"""Public input event decoding and output observation; no SRAM-to-golden path."""
import asyncio
from contextlib import suppress

from toffee import Bundle, DriveStable, RisingEdge, on

from bpuverify.mbtb.model.semantic import Branch, Events, Feedback, Source
from bpuverify.mbtb.monitor.decode import _decode


def decode_feedback(train):
    sources = tuple(tuple(Source(bool(source.rawHit.as_int()), source.position.as_int(),
        source.attribute.branchType.as_int(), source.attribute.rasAction.as_int(), source.counter_value.as_int())
        for source in row) for row in train.meta_entries)
    branches = tuple(Branch(branch.target.as_int(), bool(branch.taken.as_int()), branch.position.as_int(),
        branch.branch_type.as_int(), branch.ras_action.as_int(), bool(branch.mispredict.as_int()))
        for branch in train.branches if branch.valid.as_int())
    return Feedback((train.start_pc0.as_int(), train.start_pc1.as_int()), sources, branches)


def decode_events(sample):
    row = sample.lookup
    return Events(pc=row.start_pc.as_int(), select=bool(row.s0_fire.as_int()),
        advance=bool(row.s1_fire.as_int()), consume=bool(row.s2_fire.as_int()),
        feedback=decode_feedback(sample.train) if sample.train_valid.as_int() else None,
        enabled=bool(sample.enabled.as_int()), ready=bool(sample.ready.as_int()), reset=bool(sample.reset.as_int()))


class MbtbSemanticMonitor:
    def __init__(self, dut, ports):
        self.clock = ports.lookup.clock
        self.inputs = Bundle(reset=dut.reset, enabled=ports.control.bits.enable,
            ready=ports.status.bits.reset_done, lookup=ports.lookup.bits,
            train_valid=ports.training.valid, train=ports.training.bits).compile_sampler()
        self.outputs = Bundle(enabled=ports.control.bits.enable, prediction=ports.prediction.bits).compile_sampler()
        self.launched = Events(enabled=False, ready=False)
        self.execution = None
        self.subscriptions = []

    def start(self, execution, checker):
        self.execution = execution

        def inputs(event):
            launched = decode_events(self.inputs())
            checker.capture_input(event, self.launched)
            self.launched = launched

        def outputs(event):
            row = self.outputs()
            checker.capture_output(event, _decode(row.prediction), enabled=bool(row.enabled.as_int()))

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
