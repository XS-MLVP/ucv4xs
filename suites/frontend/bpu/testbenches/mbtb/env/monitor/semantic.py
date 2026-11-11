"""Public input event decoding and output observation; no SRAM-to-golden path."""
import asyncio
from contextlib import suppress
from dataclasses import replace

from toffee import Bundle, DriveStable, RisingEdge, on

from suites.frontend.bpu.testbenches.mbtb.model.semantic import WAYS
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Branch
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Events
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Feedback
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Source
from suites.frontend.bpu.testbenches.mbtb.env.monitor.decode import _decode
from suites.frontend.bpu.testbenches.mbtb.env.bundle.values import _plain
from suites.frontend.bpu.testbenches.mbtb.env.driver.feedback import observed_mbtb_feedback


def decode_feedback(train):
    # The victim's exposed identity is real input. Its counter and attribute
    # are not on this wire; they are not consulted for victim admission.
    sources = tuple(tuple(
        Source(bool(source.rawHit.as_int()), source.position.as_int(),
               source.attribute.branchType.as_int() if way<WAYS else 0,
               source.attribute.rasAction.as_int() if way<WAYS else 0,
               source.counter_value.as_int() if way<WAYS else 0)
        for way,source in enumerate(row))
        for row in train.meta_entries)
    branches = tuple(Branch(branch.target.as_int(), bool(branch.taken.as_int()), branch.position.as_int(),
        branch.branch_type.as_int(), branch.ras_action.as_int(), bool(branch.mispredict.as_int()))
        for branch in train.branches if branch.valid.as_int())
    return Feedback((train.start_pc0.as_int(), train.start_pc1.as_int()), sources, branches)


def decode_events(sample):
    row = sample.lookup
    return Events(pc=row.start_pc.as_int(), select=bool(row.s0_fire.as_int()),
        advance=bool(row.s1_fire.as_int()), consume=bool(row.s2_fire.as_int()),
        last_stage=bool(row.s3_fire.as_int()),
        victim_taken=tuple(bool(value.as_int()) for value in row.victim_taken),
        feedback=decode_feedback(sample.train) if sample.train_valid.as_int() else None,
        enabled=bool(sample.enabled.as_int()), ready=bool(sample.ready.as_int()), reset=bool(sample.reset.as_int()))


class MbtbSemanticMonitor:
    def __init__(self, dut, ports,*,training_inputs=None,lookup_inputs=None):
        self.clock = ports.lookup.clock
        self.inputs = Bundle(reset=dut.reset, enabled=ports.control.bits.enable,
            ready=ports.status.bits.reset_done, lookup=ports.lookup.bits,
            train_valid=ports.training.valid, train=ports.training.bits).compile_sampler()
        self.outputs = Bundle(enabled=ports.control.bits.enable, prediction=ports.prediction.bits).compile_sampler()
        self.launched = Events(enabled=False, ready=False)
        self.execution = None
        self.subscriptions = []
        self.training_inputs=training_inputs
        self.lookup_inputs=lookup_inputs

    def start(self, execution, checker):
        self.execution = execution
        previous_wire=None
        preedge_ready=False

        def inputs(event):
            nonlocal preedge_ready
            # Readiness is a DUT output and must be its pre-edge value. Driven
            # inputs are captured at the actual rising edge below: cancellation
            # after this preview can still withdraw an unaccepted valid beat.
            preedge_ready=bool(self.inputs().ready.as_int())
            if self.training_inputs is not None and checker.failure is None:
                try:
                    prior=self.launched
                    # The saved actual rising-edge input is consumed one
                    # half-tick later; this model phase is not its offer time.
                    self.training_inputs.observe(event.tick-1,reset=prior.reset,
                        ready=prior.ready,enabled=prior.enabled,feedback=previous_wire)
                except Exception as error:checker.failure=error
            if self.lookup_inputs is not None and checker.failure is None:
                try:self.lookup_inputs.observe(event.tick-1,self.launched)
                except Exception as error:checker.failure=error
            checker.capture_input(event, self.launched)

        def outputs(event):
            nonlocal previous_wire
            actual_inputs=self.inputs()
            launched=replace(decode_events(actual_inputs),ready=preedge_ready)
            wire=(observed_mbtb_feedback(dict(ready=1,bits=_plain(actual_inputs.train)))
                  if actual_inputs.train_valid.as_int() else None)
            row = self.outputs()
            checker.capture_output(event, _decode(row.prediction), enabled=bool(row.enabled.as_int()))
            if self.lookup_inputs is not None and checker.failure is None:
                try:self.lookup_inputs.observe_output(event.tick)
                except Exception as error:checker.failure=error
            self.launched=launched
            previous_wire=wire

        async def delivered(_):
            pass

        for trigger, capture in ((DriveStable(self.clock), inputs), (RisingEdge(self.clock), outputs)):
            spec = on(trigger, delivery='lossless', capacity=64, capture=capture)(delivered)
            self.subscriptions.append(execution.subscribe(spec.bind()))
        return self

    async def aclose(self):
        for subscription in self.subscriptions:
            self.execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await subscription.task
        self.subscriptions.clear()
