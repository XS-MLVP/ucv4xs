"""Public-port adapter: signals end here; references receive semantic events."""
import asyncio
from contextlib import suppress

from toffee import Bundle, DriveStable, RisingEdge, on

from bpuverify.ubtb.model.semantic import UbtbEvents
from bpuverify.common.model.address import decode_pruned_pc
from bpuverify.ubtb.monitor.decode import _decode_prediction_sample
from bpuverify.ubtb.transaction.types import (
    BranchTraining, PredictRequest, UbtbBatchTraining, UbtbBranchFeedback,
)


def _branch(sample, kind, **extra):
    values = {name: getattr(sample, name).as_int() for name in (
        'target', 'taken', 'position', 'branch_type', 'ras_action', 'mispredict')}
    values['target'] = decode_pruned_pc(values['target'])
    return kind(**extra, **values)


def decode_events(sample):
    """Decode only module inputs; no internal hit/way/counter is consulted."""
    fast = None
    if sample.fast_valid.as_int():
        fast = _branch(sample.fast.branch, BranchTraining, pc=decode_pruned_pc(sample.fast.start_pc.as_int()))
    resolve = None
    if sample.resolve_valid.as_int():
        resolve = UbtbBatchTraining(decode_pruned_pc(sample.resolve.start_pc.as_int()), tuple(
            _branch(branch, UbtbBranchFeedback, valid=branch.valid.as_int())
            for branch in sample.resolve.branches))
    return UbtbEvents(
        predict=(PredictRequest(decode_pruned_pc(sample.lookup.start_pc.as_int()))
                 if sample.lookup.s0_fire.as_int() else None),
        fast_feedback=fast, resolve_feedback=resolve,
        consume=bool(sample.lookup.s1_fire.as_int()),
        enabled=bool(sample.enabled.as_int()), reset=bool(sample.reset.as_int()))


class UbtbSemanticMonitor:
    def __init__(self, dut, ports):
        self.clock = ports.lookup.clock
        self.inputs = Bundle(
            reset=dut.reset, enabled=ports.control.bits.enable,
            lookup=ports.lookup.bits, fast_valid=ports.fast_train.valid,
            fast=ports.fast_train.bits, resolve_valid=ports.training.valid,
            resolve=ports.training.bits,
        ).compile_sampler()
        self.outputs = Bundle(enabled=ports.control.bits.enable,
                              prediction=ports.prediction.bits).compile_sampler()
        self.subscriptions = []
        self.execution = None
        self.launched = UbtbEvents(enabled=False)

    def start(self, execution, checker):
        self.execution = execution

        def inputs(event):
            launched = decode_events(self.inputs())
            # Picker's RiseWrite input reads expose pending driver values.
            # They are committed at the following rise, then consumed by the
            # DUT on the next clock. Decode launches here, deliver the previous
            # launch as the hardware event. This belongs to the adapter, not
            # the event-level cache algorithm or a wait in a testcase.
            checker.capture_input(event, self.launched)
            self.launched = launched

        def outputs(event):
            row = self.outputs()
            checker.capture_output(event, _decode_prediction_sample(row.prediction),
                                   enabled=bool(row.enabled.as_int()))

        async def delivered(_):
            pass

        for trigger, capture in ((DriveStable(self.clock), inputs),
                                 (RisingEdge(self.clock), outputs)):
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
