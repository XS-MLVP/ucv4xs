"""Read-only pre/post-edge observation of DelayN and FallThroughPredictor.

No additional drive, no optional fabricated leaves, and no generated-RTL edits.
The first two CSR sampling edges establish the unreset delay's defined state.
"""
import asyncio
from contextlib import suppress

from toffee import Bundle, DriveStable, RisingEdge, on

from suites.frontend.bpu.testbenches.bpu.model.parent_primitives import ENABLES
from suites.frontend.bpu.testbenches.shared.env.memory_direct import memory_signal, memory_signal_names
from suites.frontend.bpu.testbenches.bpu.env.bundle.plain_sampler import compile_plain


class ParentPrimitiveMonitor:
    def __init__(self, agent, checker):
        self.agent, self.checker = agent, checker
        names = memory_signal_names(agent.dut)
        anchor, = [name for name in names if name.endswith('.fallThrough.io_stageCtrl_s0_fire')]
        prefix = anchor.removeprefix('TOP.').removesuffix('fallThrough.io_stageCtrl_s0_fire')
        signal = lambda field: memory_signal(agent.dut, prefix + field)
        self.before = compile_plain(Bundle(
            # Read the native consumed inputs, not an input XData's pending
            # Rise-write cache. Native trace aliases point to the current RTL
            # input memory, preserving the physical two-edge delay contract.
            controls=Bundle(**{name: signal(f'csrCtrl_delay.io_in_{name}Enable') for name in ENABLES}),
            fire=signal('fallThrough.io_stageCtrl_s0_fire'), pc=signal('fallThrough.io_startPc_addr')))
        self.actual = compile_plain(Bundle(
            delayed=Bundle(**{name: signal(f'csrCtrl_delay.io_out_{name}Enable') for name in ENABLES}),
            enabled=Bundle(**{name: signal(name + '.io_enable') for name in (*ENABLES, 'utage')}),
            fallthrough=Bundle(target=signal('fallThrough.io_prediction_target_addr'),
                               position=signal('fallThrough.io_prediction_cfiPosition')),
            diagnostic=Bundle(ubtb_hit=signal('ubtb.s1_hit'), ubtb_taken=signal('ubtb.io_prediction_bits_taken'),
                s1_taken=signal('s1_prediction_taken'), reset=signal('reset'),
                public_valid=signal('io_toFtq_prediction_valid'),
                public_pc=signal('io_toFtq_prediction_bits_startPc_addr'),
                public_taken=signal('io_toFtq_prediction_bits_taken'))))
        self.pending = None
        self.subscriptions = []

    def start(self):
        async def delivered(_):
            pass

        def preedge(event):
            if self.pending is not None and self.checker.failure is None:
                self.checker.failure = AssertionError('unconsumed primitive pre-edge snapshot')
            self.pending = event.tick, self.before()

        def rising(event):
            if self.pending is None:
                if self.checker.last_tick is not None:
                    self.checker.failure = AssertionError('missing primitive pre-edge snapshot')
                return  # A scope may be installed after its first pre-edge.
            tick, before = self.pending
            self.pending = None
            self.checker.capture(before, self.actual(), pre_tick=tick, tick=event.tick)

        for trigger, capture in ((DriveStable, preedge), (RisingEdge, rising)):
            self.subscriptions.append(self.agent._execution.subscribe(on(
                trigger(self.agent.dut.clock), capture=capture, delivery='lossless', capacity=64)(delivered).bind()))

    async def aclose(self):
        for subscription in self.subscriptions:
            self.agent._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await subscription.task
        self.subscriptions.clear()
