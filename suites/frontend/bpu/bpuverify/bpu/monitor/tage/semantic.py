"""Component inputs are evaluated RTL IO, not pending top-level RiseWrites."""
import asyncio
from contextlib import suppress

from toffee import DriveStable, RisingEdge, on

from bpuverify.bpu.bundle.tage_semantic import semantic_binding, HISTORY_PORTS
from bpuverify.tage.monitor.decode import _decode
from bpuverify.tage.model.semantic import Base, Context, Events
from bpuverify.tage.monitor.semantic import feedback_value


def consumed_context(rows):
    values = [0] * 19
    for index, row in zip(HISTORY_PORTS, rows, strict=True):
        values[index] = row.foldedHist.as_int()
    return Context(tuple(values))


def component_events(sample):
    lookup = sample.lookup
    return Events(lookup.start_pc.as_int(), consumed_context(lookup.history),
        tuple(value.as_int() for value in lookup.main_btb.s1_positions),
        bool(lookup.s0_fire.as_int()), bool(lookup.s1_fire.as_int()),
        feedback_value(sample.train, context_decoder=consumed_context) if sample.train_valid.as_int() else None,
        bool(sample.enabled.as_int()), bool(sample.ready.as_int()), bool(sample.reset.as_int()))


class TageSemanticComponentMonitor:
    def __init__(self, agent):
        self.agent, self.binding = agent, semantic_binding(agent)
        self.subscriptions = []

    def start(self, checker):
        inputs, outputs = self.binding.bits.inputs.compile_sampler(), self.binding.bits.outputs.compile_sampler()
        def capture_input(event):
            row = inputs()
            checker.capture_input(event, component_events(row), resolve_slots=tuple(
                branch.position.as_int() if branch.valid.as_int() else None for branch in row.train.branches))
        def capture_output(event):
            row = outputs()
            # TAGE consumes only live base valid/direction/confidence. Branch
            # positions are already owned in its independently latched S1
            # frame; these unused MainBTB leaves are absent from emitted RTL.
            bases = tuple(Base(valid=bool(entry.valid.as_int()), taken=bool(entry.bits.taken.as_int()),
                               confident=bool(conf.as_int())) for entry, conf in zip(
                                   row.bases.main_btb.result, row.bases.main_btb.baseConf, strict=True))
            checker.capture_output(event, _decode(row.prediction), bases=bases,
                enabled=bool(row.enabled.as_int()), extras=dict(
                    fast_valids=tuple(entry.valid.as_int() for entry in row.fast),
                    fast_takens=tuple(entry.bits.as_int() for entry in row.fast),
                    sc_counters=tuple(entry.bits_value.as_int() for entry in row.sc)))
        async def delivered(_):
            pass
        for trigger, capture in ((DriveStable(self.binding.clock), capture_input), (RisingEdge(self.binding.clock), capture_output)):
            self.subscriptions.append(self.agent._execution.subscribe(on(trigger, delivery='lossless',
                capacity=64, capture=capture)(delivered).bind()))
        return self

    async def aclose(self):
        for subscription in self.subscriptions:
            self.agent._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await subscription.task
        self.subscriptions.clear()
