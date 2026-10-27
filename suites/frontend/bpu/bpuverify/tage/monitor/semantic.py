"""Public event decoder and sampled result adapter; no table-state oracle."""
import asyncio
from contextlib import suppress

from toffee import Bundle, DriveStable, RisingEdge, on

from bpuverify.tage.model.semantic import Base, Branch, Context, Events, Feedback, Hint
from bpuverify.tage.monitor.decode import _decode
from bpuverify.common.bundle.bindings import bind_bundle


def context_value(histories):
    return Context(tuple(row.foldedHist.as_int() for row in histories))


def bases_value(lookup):
    return tuple(Base(bool(entry.valid.as_int()), entry.bits.cfiPosition.as_int(), bool(entry.bits.taken.as_int()),
        bool(conf.as_int()), entry.bits.attribute.branchType.as_int())
        for entry, conf in zip(lookup.main_btb.result, lookup.main_btb.baseConf, strict=True))


def hint_value(row):
    provider = bool(row.hasProvider.as_int())
    return Hint(provider, bool(row.hasAlt.as_int()), bool(row.useProvider.as_int()),
        row.providerTableIdx.as_int() if provider else 0, row.providerWayIdx.as_int() if provider else 0,
        row.providerTakenCtr_value.as_int() if provider else 0, row.providerUsefulCtr_value.as_int() if provider else 0,
        bool(row.altOrBasePred.as_int()), bool(row.altConf.as_int()))


def feedback_value(train, *, context_decoder=context_value):
    sources = tuple(source for row in train.mbtb_meta for source in row)
    branches = []
    for branch in train.branches:
        if not branch.valid.as_int():
            continue
        position = branch.position.as_int()
        matching = [slot for slot, source in enumerate(sources)
                    if source.rawHit.as_int() and source.position.as_int() == position]
        slot = matching[0] if matching else None
        branches.append(Branch(position, bool(branch.taken.as_int()), branch.branch_type.as_int(),
            bool(branch.mispredict.as_int()), bool(matching),
            sources[slot].counter_value.as_int() if slot is not None else 0,
            hint_value(train.tage_meta[slot]) if slot is not None else Hint()))
    return Feedback(train.start_pc.as_int(), context_decoder(train.history), tuple(branches))


def events_value(sample):
    lookup = sample.lookup
    return Events(lookup.start_pc.as_int(), context_value(lookup.history),
        tuple(value.as_int() for value in lookup.main_btb.s1_positions),
        bool(lookup.s0_fire.as_int()), bool(lookup.s1_fire.as_int()),
        feedback_value(sample.train) if sample.train_valid.as_int() else None,
        bool(sample.enabled.as_int()), bool(sample.ready.as_int()), bool(sample.reset.as_int()))


class TageSemanticMonitor:
    def __init__(self, dut, ports):
        self.clock = ports.lookup.clock
        self.inputs = Bundle(reset=dut.reset, enabled=ports.control.bits.enable,
            ready=ports.status.bits.reset_done, lookup=ports.lookup.bits,
            train_valid=ports.training.valid, train=ports.training.bits).compile_sampler()
        io = bind_bundle(dut, ('io',), name='tage.semantic.io').bits
        self.outputs = Bundle(prediction=ports.prediction.bits, enabled=ports.control.bits.enable,
            bases=ports.lookup.bits, fast=io.prediction.fastTakenVec, sc=io.toSc_providerTakenCtrVec).compile_sampler()
        self.launched = Events(enabled=False, ready=False)
        self.execution = None
        self.subscriptions = []

    def start(self, execution, checker):
        self.execution = execution

        def inputs(event):
            launched = events_value(self.inputs())
            checker.capture_input(event, self.launched)
            self.launched = launched

        def outputs(event):
            row = self.outputs()
            extras = dict(fast_valids=tuple(entry.valid.as_int() for entry in row.fast),
                fast_takens=tuple(entry.bits.as_int() for entry in row.fast),
                sc_counters=tuple(entry.bits_value.as_int() for entry in row.sc))
            checker.capture_output(event, _decode(row.prediction), bases=bases_value(row.bases),
                                   enabled=bool(row.enabled.as_int()), extras=extras)

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
