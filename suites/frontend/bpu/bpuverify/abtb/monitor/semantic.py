"""Decode public input operations; signal binding and launch phase end here."""
import asyncio
from contextlib import suppress

from toffee import Bundle, DriveStable, RisingEdge, on

from bpuverify.abtb.model.semantic import Events, Feedback, Source
from bpuverify.abtb.monitor.decode import _decode


def decode_feedback(train):
    meta, branch = train.meta, train.branch
    sources = tuple(Source(bool(entry.hit.as_int()), entry.position.as_int(),
        entry.attribute.branchType.as_int(), entry.attribute.rasAction.as_int(), entry.targetLowerBits.as_int())
        for entry in meta.entries)
    return Feedback(train.start_pc.as_int(), branch.target.as_int(), bool(branch.taken.as_int()),
        branch.position.as_int(), branch.branch_type.as_int(), branch.ras_action.as_int(),
        bool(meta.valid.as_int()), meta.setIdx.as_int(), meta.bankMask.as_int(), sources)


def decode_events(sample):
    row = sample.lookup
    return Events(read_pc=row.start_pc.as_int(), history=row.path_hash.as_int() % 16,
        select=bool(row.s0_fire.as_int()), match_pc=row.new_start_pc.as_int(),
        consume=bool(row.s1_fire.as_int()), remember=bool(row.s2_fire.as_int()),
        override='s3' if row.s3_override.as_int() else 's2' if row.s2_override.as_int() else None,
        override_pc=row.override_start_pc.as_int(), redirect=bool(row.redirect.as_int()),
        feedback=decode_feedback(sample.train) if sample.train_valid.as_int() else None,
        enabled=bool(sample.enabled.as_int()), ready=bool(sample.ready.as_int()), reset=bool(sample.reset.as_int()))


class AbtbSemanticMonitor:
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
