"""Normalize native phases into immutable domain cycles; no reference/checker."""
import asyncio
from contextlib import asynccontextmanager, suppress

from toffee import DriveStable, RisingEdge, XPhase, on

from .ports import snapshot
from .types import Cycle


class CycleAssembler:
    """Protocol association, independently testable without a simulator."""
    def __init__(self):
        self.pending = None
        self.last_tick = None
        self.completed = 0

    def accept(self, event, boundary):
        if event.phase is XPhase.DRIVE_STABLE:
            if self.pending is not None:
                raise AssertionError('duplicate preedge or missing rising observation')
            if self.last_tick is not None and event.tick != self.last_tick + 1:
                raise AssertionError('missing preedge boundary')
            self.pending = (event.tick, boundary)
            return None
        if event.phase is not XPhase.RISING_STABLE:
            raise AssertionError('unsupported sampling phase')
        if self.pending is None or event.tick != self.pending[0] + 1:
            raise AssertionError('rising requires the immediately preceding preedge')
        self.completed += 1
        result = Cycle(self.completed, self.pending[1], boundary)
        self.last_tick, self.pending = event.tick, None
        return result

    def finish(self):
        if self.pending is not None:
            raise AssertionError('unconsumed preedge at monitor close')
        if not self.completed:
            raise AssertionError('no complete observation cycles')


class ManagerMonitor:
    def __init__(self, ports):
        self.clock = ports.clock
        self.sampler = ports.observed.compile_sampler()
        self.assembler = CycleAssembler()
        self.latest = None
        self.active = False

    @asynccontextmanager
    async def observe(self, execution, publish):
        if self.active:
            raise RuntimeError('Manager monitor already active')
        self.active = True
        subscriptions = []

        def capture(event):
            cycle = self.assembler.accept(event, snapshot(self.sampler()))
            if cycle is not None:
                self.latest = cycle
                publish(cycle)

        async def delivered(_):
            pass

        try:
            for trigger in (DriveStable, RisingEdge):
                spec = on(trigger(self.clock), delivery='lossless', capacity=64,
                          capture=capture)(delivered)
                subscriptions.append(execution.subscribe(spec.bind()))
            yield self
            self.assembler.finish()
        finally:
            for subscription in subscriptions:
                execution.reactor.cancel_subscription(subscription)
            for subscription in subscriptions:
                if subscription.task is not None:
                    with suppress(asyncio.CancelledError):
                        await subscription.task
            self.active = False
