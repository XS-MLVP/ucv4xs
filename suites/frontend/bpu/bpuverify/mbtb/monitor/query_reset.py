"""Passive lossless capture: real source snapshot -> response or reset event."""
import asyncio
from contextlib import suppress
from copy import deepcopy
from toffee import RisingEdge, on
from bpuverify.common.model.query_lifetime import QueryLease

class QueryMonitor:

    def __init__(self, agent, program, checks):
        self.agent, self.program, self.checks = (agent, program, checks)
        self.lease = QueryLease()
        self.failure = self.subscription = None
        self.snapshot_frozen = None
        self.actual_response = None
        self.previous_same_pc_is_not_this_request = False

    def capture(self, event):
        if self.failure is not None or self.lease.reset_tick is not None:
            return
        try:
            reference = self.agent.reference
            self.checks.check(event.tick - 1, reference.input_tick, 'current semantic input boundary')
            self.checks.check(event.tick, reference.expected[-1][0], 'current semantic output boundary')
            events, model = (reference.events, reference.model)
            if events.reset:
                self.lease.reset(event.tick)
                return
            selected = events.select and events.enabled and events.ready
            pc = events.pc
            snapshot, output = (model.read, model.frame)
            if selected:
                self.checks.check(self.program.old[0].pc, pc, 'one actual original query before reset')
                self.lease.accept(snapshot, event.tick)
                self.snapshot_frozen = deepcopy(snapshot)
                self.previous_same_pc_is_not_this_request = output is not None and output.pc == pc and output is not snapshot
            if self.lease.disposition is None and self.lease.response(output, event.tick):
                expected = output.values(True)
                actual = self.agent.prediction_monitor.sample_at(event).value
                self.checks.old_response(expected, actual)
                self.actual_response = actual
        except Exception as error:
            self.failure = error

    def start(self):

        async def delivered(_):
            pass
        self.subscription = self.agent._execution.subscribe(on(RisingEdge(self.agent.dut.clock), capture=self.capture, delivery='lossless', capacity=64)(delivered).bind())
        return self

    def status(self):
        if self.failure is not None:
            raise self.failure
        return self.lease.state()

    async def aclose(self):
        if self.subscription is not None:
            self.agent._execution.reactor.cancel_subscription(self.subscription)
            if self.subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await self.subscription.task
