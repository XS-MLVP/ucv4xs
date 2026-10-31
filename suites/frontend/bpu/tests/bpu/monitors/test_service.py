"""The same SDK transfer lifecycle supports one-port indirect target service."""
from types import SimpleNamespace as NS
import pytest
from toffee import Bundle,ClockCycles,Execution,MemoryBackend,ReadyValid,Role
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.bpu.monitor.service import ServiceMonitor
from tests.bpu.monitors.test_tage_service import Signal


async def test_one_port_full_target_transfers_are_immutable_and_all_tasks_are_owned():
    clock=object();writes=[];rows=[];requested=[]
    async with Execution(MemoryBackend(clock)) as execution:
        port=ReadyValid(clock=clock,valid=Signal(1),ready=Signal(0),role=Role.MONITOR,
            bits=Bundle(row=Signal(7),valid=Signal(1),tag=Signal(3),confidence=Signal(3),useful=Signal(0),
                offset=Signal(0x1000),pointer=Signal(2),pc_region=Signal(0),mask=Signal((1<<36)-1)),name='indirect-service')
        binding=PortBinding(clock,Bundle(write=Bundle(valid=port.valid,ready=port.ready,bits=port.bits)),'indirect')
        def factory(agent,**kwargs):requested.append(kwargs);return binding,(port,)
        checker=NS(table=2,bank=0,observe_retention=True,raise_failure=lambda:None,
            capture_state=lambda event,row:rows.append((event.tick,row)),
            write_accepted=lambda index,transfer:writes.append((index,transfer.accepted_tick,transfer.value)))
        agent=NS(_execution=execution)
        monitor=ServiceMonitor(agent,checker,binding=factory(agent,table=2,bank=0,include_retention=True))
        async with monitor:
            await ClockCycles(clock,2);assert not writes and len(rows)==2
            port.ready.value=1;await ClockCycles(clock,1)
            port.bits.pointer.value=3;port.bits.offset.value=0x1800;await ClockCycles(clock,1)
            port.valid.value=0;await ClockCycles(clock,1)
        assert requested==[dict(table=2,bank=0,include_retention=True)]
        assert [(index,tick,bits['pointer'],bits['offset']) for index,tick,bits in writes]==[(0,6,2,0x1000),(0,8,3,0x1800)]
        assert not monitor.tasks and monitor.subscription is None
        assert all(bits['mask']==(1<<36)-1 for _,_,bits in writes)
        with pytest.raises(RuntimeError,match='single-use'):await monitor.__aenter__()
        count=len(rows);await ClockCycles(clock,2);assert len(rows)==count
