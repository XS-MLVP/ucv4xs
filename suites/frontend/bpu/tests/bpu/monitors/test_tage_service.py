"""Service observations use SDK transfer snapshots and own every watcher/task."""
import asyncio
from types import SimpleNamespace as NS

import pytest
from toffee import Bundle,ClockCycles,Execution,MemoryBackend,ReadyValid,Role

from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.bpu.monitor.tage import service as module


class Signal:
    def __init__(self,value=0):self.value=value


def fixture(clock,execution,monkeypatch,*,fail_at=None):
    ports=tuple(ReadyValid(clock=clock,valid=Signal(),ready=Signal(),role=Role.MONITOR,
        bits=Bundle(row=Signal(11+way),valid=Signal(1),tag=Signal(16+way),counter=Signal(7*way)),
        name=f'write-{way}') for way in range(2))
    binding=PortBinding(clock,Bundle(writes=tuple(Bundle(valid=port.valid,ready=port.ready,bits=port.bits)
        for port in ports)),'service-fake')
    monkeypatch.setattr(module,'service_binding',lambda agent,**kwargs:(binding,ports))
    rows,writes=[],[]
    errors=[ValueError('first-'+str(index)) for index in range(2)]
    def capture(event,row):
        if fail_at=='capture':raise errors[0]
        rows.append((event.tick,row))
    def accepted(way,transfer):
        if fail_at=='write':raise errors[way]
        writes.append((way,transfer.accepted_tick,transfer.value))
    checker=NS(table=3,bank=0,raise_failure=lambda:None,capture_state=capture,write_accepted=accepted)
    return module.TageServiceMonitor(NS(_execution=execution),checker),ports,rows,writes,errors


async def test_stalled_ports_produce_no_transfer_then_two_full_immutable_transfers_per_owner(monkeypatch):
    clock=object()
    async with Execution(MemoryBackend(clock)) as execution:
        monitor,ports,rows,writes,_=fixture(clock,execution,monkeypatch)
        async with monitor:
            for port in ports:port.valid.value=1
            await ClockCycles(clock,2)
            assert not writes and len(rows)==2
            for port in ports:port.ready.value=1
            await ClockCycles(clock,1)
            for port in ports:port.bits.row.value+=10
            await ClockCycles(clock,1)
            for port in ports:port.valid.value=0
            await ClockCycles(clock,1)
            monitor.raise_failure()
            for way in range(2):
                assert [(tick,payload['row']) for owner,tick,payload in writes if owner==way]==[(6,11+way),(8,21+way)]
        assert monitor.subscription is None and not monitor.tasks
        count=len(rows)
        await ClockCycles(clock,2)
        assert len(rows)==count and len(writes)==4
        with pytest.raises(RuntimeError,match='single-use'):await monitor.__aenter__()


@pytest.mark.parametrize('point',('capture','write'))
async def test_callback_failure_preserves_first_error_without_escaping_the_native_pump(monkeypatch,point):
    clock=object()
    async with Execution(MemoryBackend(clock)) as execution:
        monitor,ports,_,_,errors=fixture(clock,execution,monkeypatch,fail_at=point)
        with pytest.raises(ValueError) as caught:
            async with monitor:
                for port in ports:port.valid.value=port.ready.value=1
                await ClockCycles(clock,2)
                monitor.raise_failure()
        assert caught.value is errors[0]
        assert not monitor.tasks and monitor.subscription is None
        await ClockCycles(clock,2)


class FakeMonitor:
    def __init__(self,*,start_error=False,close_error=False):
        self.start_error,self.close_error=start_error,close_error
        self.closed=0
    def start(self,execution):
        if self.start_error:raise RuntimeError('start-failure')
    async def recv(self):await asyncio.Future()
    async def aclose(self):
        self.closed+=1
        if self.close_error:raise RuntimeError('close-failure')


@pytest.mark.parametrize('retention',(False,True))
async def test_optional_retention_is_selected_by_checker_without_changing_transfer_monitors(monkeypatch,retention):
    clock=object()
    async with Execution(MemoryBackend(clock)) as execution:
        previous,_,_,_,_=fixture(clock,execution,monkeypatch)
        previous.checker.observe_retention=retention
        bind=module.service_binding
        requested=[]
        def tracked(agent,**kwargs):
            requested.append(kwargs)
            return bind(agent,**kwargs)
        monkeypatch.setattr(module,'service_binding',tracked)
        monitor=module.TageServiceMonitor(NS(_execution=execution),previous.checker)
        assert requested==[dict(table=3,bank=0,include_retention=retention)]
        assert len(monitor.writes)==2 and all(isinstance(port,module.ReadyValidMonitor) for port in monitor.writes)
        async with monitor:await ClockCycles(clock,1)
        assert not monitor.tasks and monitor.subscription is None


@pytest.mark.parametrize('point',('start','body','close','body-and-close'))
async def test_partial_start_and_cleanup_failures_still_release_all_monitors_and_subscription(monkeypatch,point):
    clock=object()
    async with Execution(MemoryBackend(clock)) as execution:
        monitor,_,_,_,_=fixture(clock,execution,monkeypatch)
        a,b=FakeMonitor(close_error='close' in point),FakeMonitor(start_error=point=='start')
        monitor.writes=(a,b)
        primary=ValueError('body-failure')
        async def use():
            async with monitor:
                if point in ('body','body-and-close'):raise primary
        expected=ValueError if point.startswith('body') else RuntimeError if point=='start' else ExceptionGroup
        with pytest.raises(expected) as caught:await use()
        if point.startswith('body'):assert caught.value is primary
        if point=='body-and-close':assert any('cleanup failed' in note for note in primary.__notes__)
        assert a.closed==b.closed==1 and not monitor.tasks and monitor.subscription is None
        await ClockCycles(clock,2)


async def test_selected_useful_binding_uses_the_same_sdk_monitor_without_entry_payload_assumptions():
    clock=object();requested=[];writes=[]
    async with Execution(MemoryBackend(clock)) as execution:
        ports=tuple(ReadyValid(clock=clock,valid=Signal(),ready=Signal(),role=Role.MONITOR,
            bits=Bundle(row=Signal(7),value=Signal(1)),name=f'useful-{way}') for way in range(2))
        binding=PortBinding(clock,Bundle(writes=tuple(Bundle(valid=p.valid,ready=p.ready,bits=p.bits) for p in ports)),
            'fake-useful-binding')
        def factory(agent,**kwargs):requested.append(kwargs);return binding,ports
        checker=NS(table=3,bank=0,raise_failure=lambda:None,capture_state=lambda event,row:None,
            write_accepted=lambda way,transfer:writes.append((way,transfer.value)))
        monitor=module.TageServiceMonitor(NS(_execution=execution),checker,binding_factory=factory)
        assert requested==[dict(table=3,bank=0,include_retention=False)]
        async with monitor:
            ports[0].valid.value=ports[0].ready.value=1
            await ClockCycles(clock,1)
            ports[0].bits.row.value=9
            await ClockCycles(clock,1)
            ports[0].valid.value=0
            await ClockCycles(clock,1)
        assert writes==[(0,dict(row=7,value=1)),(0,dict(row=9,value=1))]
        assert not monitor.tasks and monitor.subscription is None
