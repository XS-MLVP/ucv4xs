"""Public ITTAGE port decoding; no internal table/buffer state observation."""
import asyncio
from contextlib import suppress

from toffee import Bundle, DriveStable, RisingEdge, on

from bpuverify.common.model.folded_history import PHR_FOLD_LAYOUT
from bpuverify.ittage.model.semantic import Context, Events, HISTORY_LENGTHS, Metadata, Outcome, SETS
from bpuverify.ittage.monitor.decode import _decode


def context_value(histories):
    values = {layout: row.foldedHist.as_int() for layout, row in zip(PHR_FOLD_LAYOUT, histories, strict=True)}
    return Context(tuple((values[length, min(length, sets.bit_length() - 1)],
                          values[length, min(length, 7)], values[length, min(length, 6)])
                         for length, sets in zip(HISTORY_LENGTHS, SETS, strict=True)))


def metadata_value(meta):
    """Decode the training snapshot embedded in one FTQ feedback beat.

    The master ``valid`` bit is the publication qualification of the original
    ITTAGE query. When it is clear, the remaining fields are unrelated
    register residue: they are not a provider or allocation snapshot and must
    not be turned into a synthetic legal metadata object.
    """

    valid = getattr(meta, 'valid', None)
    if valid is not None and not valid.as_int():
        return Metadata(published=False)
    provider = meta.provider.bits.as_int() if meta.provider.valid.as_int() else None
    alternate = meta.altProvider.bits.as_int() if meta.altProvider.valid.as_int() else None
    return Metadata(
        provider=provider, confidence=meta.providerCnt_value.as_int() if provider is not None else 0,
        useful=meta.providerUsefulCnt_value.as_int() if provider is not None else 0,
        provider_target=meta.providerTarget_addr.as_int() * 2 if provider is not None else 0,
        alternate=alternate, alternate_confidence=meta.altProviderCnt_value.as_int() if alternate is not None else 0,
        alternate_target=meta.altProviderTarget_addr.as_int() * 2 if alternate is not None else 0,
        differs=bool(meta.altDiffers.as_int()) if alternate is not None else False,
        allocation=meta.allocate.bits.as_int() if meta.allocate.valid.as_int() else None)



def decode_events(row):
    feedback = None
    if row.train_valid.as_int():
        selected = [branch for branch in row.train.branches if branch.valid.as_int()
                    and branch.taken.as_int() and branch.branch_type.as_int() == 3
                    and not branch.ras_action.as_int() & 1]
        if len(selected) > 1:
            raise ValueError('ITTAGE feedback has multiple qualifying indirect branches')
        if selected:
            branch, = selected
            feedback = Outcome(row.train.start_pc.as_int() * 2,
                context_value(row.train.folded_history), metadata_value(row.train.meta),
                branch.target.as_int() * 2, mispredict=bool(branch.mispredict.as_int()))
    return Events(
        pc=row.lookup.start_pc.as_int() * 2 if row.lookup.s0_fire.as_int() else None,
        context=context_value(row.lookup.folded_history),
        access=bool(row.lookup.s1_fire.as_int()), select=bool(row.lookup.s2_fire.as_int()),
        feedback=feedback, enabled=bool(row.enabled.as_int()),
        ready=bool(row.ready.as_int()), reset=bool(row.reset.as_int()))


class IttageSemanticMonitor:
    def __init__(self, dut, ports):
        self.clock = ports.lookup.clock
        self.inputs = Bundle(reset=dut.reset, enabled=ports.control.bits.enable,
            ready=ports.status.bits.reset_done, lookup=ports.lookup.bits,
            train_valid=ports.training.valid, train=ports.training.bits).compile_sampler()
        self.outputs = Bundle(prediction=ports.prediction.bits, enabled=ports.control.bits.enable,
                              consume=ports.lookup.bits.s3_fire).compile_sampler()
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
            checker.capture_output(event, _decode(row.prediction),
                                   visible=bool(row.enabled.as_int() and row.consume.as_int()))

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
