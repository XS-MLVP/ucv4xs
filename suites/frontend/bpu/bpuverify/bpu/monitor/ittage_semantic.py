"""Decode observed component-interface events, not internal register effects."""
import asyncio
from contextlib import suppress

from toffee import DriveStable, RisingEdge, on

from bpuverify.bpu.bundle.ittage_semantic import semantic_binding
from bpuverify.ittage.model.semantic import Context, Events, Outcome
from bpuverify.ittage.monitor.semantic import metadata_value
from bpuverify.ittage.monitor.decode import _decode


def folded_context(rows):
    return Context(tuple(tuple(getattr(row, field).as_int() for field in ('index', 'tag', 'secondary'))
                         for row in rows))


def component_events(row):
    feedback = None
    if row.train_valid.as_int():
        selected = [branch for branch in row.branches if branch.valid.as_int() and branch.taken.as_int()
                    and branch.branch_type.as_int() == 3 and not branch.ras_action.as_int() & 1]
        if len(selected) > 1:
            raise ValueError('component interface contains multiple qualifying indirect branches')
        if selected:
            branch, = selected
            feedback = Outcome(row.train_pc.as_int() * 2, folded_context(row.train_context),
                metadata_value(row.train_meta), branch.target.as_int() * 2,
                mispredict=bool(branch.mispredict.as_int()))
    return Events(pc=row.pc.as_int() * 2 if row.accept.as_int() else None,
        context=folded_context(row.context), access=bool(row.access.as_int()), select=bool(row.select.as_int()),
        feedback=feedback, enabled=bool(row.enabled.as_int()), ready=bool(row.ready.as_int()),
        reset=bool(row.reset.as_int()))


class IttageSemanticComponentMonitor:
    def __init__(self, agent):
        self.agent = agent
        self.binding = semantic_binding(agent)
        self.subscriptions = []

    def start(self, checker):
        inputs = self.binding.bits.inputs.compile_sampler()
        outputs = self.binding.bits.outputs.compile_sampler()

        def capture_input(event):
            # These are evaluated RTL component inputs, not top-level XData
            # pending RiseWrite buffers. Do not add the standalone launch delay.
            checker.capture_input(event, component_events(inputs()))

        def capture_output(event):
            row = outputs()
            baseline = (row.baseline.corrected_target if row.baseline.overridden.as_int()
                        else row.baseline.early_target).as_int()
            checker.capture_output(event, _decode(row.prediction),
                visible=bool(row.enabled.as_int() and row.consume.as_int()), baseline=baseline)

        async def delivered(_):
            pass

        for trigger, capture in ((DriveStable(self.binding.clock), capture_input),
                                 (RisingEdge(self.binding.clock), capture_output)):
            spec = on(trigger, delivery='lossless', capacity=64, capture=capture)(delivered)
            self.subscriptions.append(self.agent._execution.subscribe(spec.bind()))
        return self

    async def aclose(self):
        for subscription in self.subscriptions:
            self.agent._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await subscription.task
        self.subscriptions.clear()
