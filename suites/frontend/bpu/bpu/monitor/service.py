"""SDK-confirmed write transfers plus compact same-cycle service observations."""
import asyncio
from collections import deque
from contextlib import suppress
from copy import deepcopy
from dataclasses import asdict

from toffee import ReadyValidMonitor,RisingEdge,on

from suites.frontend.bpu.bpu.bundle.values import _plain


def decode_short_entry(word,layout):
    """Decode only the actual native packing; golden tags stay full width."""
    tag_bits,position_bits,counter_bits,padding=layout
    value=word>>padding
    counter=value&((1<<counter_bits)-1);value>>=counter_bits
    position=value&((1<<position_bits)-1);value>>=position_bits
    tag=value&((1<<tag_bits)-1);value>>=tag_bits
    return dict(valid=bool(value),tag=tag,position=position,counter=counter)


class MainLearningReceipts:
    """Bounded actual learning/service receipts, never a per-cycle trace.

    The semantic proposal is recorded alongside hardware, not repaired from
    it. A diagnostic difference does not replace the main checker's exception.
    """
    def __init__(self,pipeline,*,alignment=0,bank=0,capacity=64):
        self.pipeline,self.key = pipeline,(alignment,bank)
        self.offers,self.services = deque(maxlen=capacity),deque(maxlen=capacity)
        self.offers_seen=self.services_seen=0

    def raise_failure(self):self.pipeline.raise_failure()

    def capture_state(self,event,row):
        parent = deepcopy(row.get('parent'))
        row = row.get('state',row)
        main = self.pipeline.model.sources.main
        expected = main.direction_proposals().get(self.key)
        if not row['direction']['valid'] and not any(port['valid'] for port in row['incoming']) and expected is None:
            return
        self.offers_seen+=1
        self.offers.append(dict(tick=event.tick,direction=deepcopy(row['direction']),
            entries=deepcopy(row['incoming']),expected=None if expected is None else asdict(expected),
            original=None if main.offered is None else asdict(main.offered.feedback),parent=parent,
            nominated=None if main.offered is None else main.offered.victims))

    def write_accepted(self,port,transfer):
        self.services_seen+=1
        self.services.append(dict(tick=transfer.accepted_tick,port=port,bits=deepcopy(transfer.value)))

    def state(self):
        return deepcopy(dict(scope=dict(alignment=self.key[0],bank=self.key[1]),
            offers=list(self.offers),services=list(self.services),offers_seen=self.offers_seen,
            services_seen=self.services_seen,truncated=self.offers_seen>len(self.offers) or self.services_seen>len(self.services)))


class ServiceMonitor:
    def __init__(self,agent,checker,*,binding):
        self.agent,self.checker=agent,checker
        binding,ports=binding
        self.binding=binding
        self.writes=tuple(ReadyValidMonitor(port,decoder=_plain,capacity=8) for port in ports)
        self.subscription=None
        self.tasks=[]
        self.failure=None
        self._used=False

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.checker.raise_failure()

    async def __aenter__(self):
        if self._used:raise RuntimeError('SRAM service monitors are single-use')
        self._used=True
        sampler=self.binding.bits.compile_sampler()
        def capture(event):
            try:self.checker.capture_state(event,_plain(sampler()))
            except Exception as error:
                if self.failure is None:self.failure=error
        async def delivered(_):pass
        async def collect(way,monitor):
            try:
                while True:self.checker.write_accepted(way,await monitor.recv())
            except asyncio.CancelledError:raise
            except Exception as error:
                if self.failure is None:self.failure=error
        try:
            self.subscription=self.agent._execution.subscribe(on(RisingEdge(self.binding.clock),
                capture=capture,delivery='lossless',capacity=64)(delivered).bind())
            for way,monitor in enumerate(self.writes):
                monitor.start(self.agent._execution)
                self.tasks.append(asyncio.create_task(collect(way,monitor),name=f'sram-service-write-{way}'))
            return self
        except BaseException as primary:
            try:await self.aclose()
            except BaseException as error:primary.add_note(f'SRAM service monitor setup cleanup failed: {error!r}')
            raise

    async def aclose(self):
        errors=[]
        for task in self.tasks:task.cancel()
        for task in self.tasks:
            try:
                with suppress(asyncio.CancelledError):await task
            except BaseException as error:errors.append(error)
        self.tasks.clear()
        for monitor in self.writes:
            try:await monitor.aclose()
            except BaseException as error:errors.append(error)
        if self.subscription is not None:
            try:
                self.agent._execution.reactor.cancel_subscription(self.subscription)
                if self.subscription.task is not None:
                    with suppress(asyncio.CancelledError):await self.subscription.task
            except BaseException as error:errors.append(error)
            finally:self.subscription=None
        if errors:raise BaseExceptionGroup('SRAM service monitor cleanup failures',errors)

    async def __aexit__(self,exc_type,exc,traceback):
        try:await self.aclose()
        except BaseException as error:
            if exc is None:raise
            exc.add_note(f'SRAM service monitor cleanup failed: {error!r}')
        if exc_type is None:self.raise_failure()
