"""Public event decoder and sampled result adapter; no table-state oracle."""
import asyncio
from contextlib import suppress
from dataclasses import replace

from toffee import Bundle, DriveStable, RisingEdge, on

from suites.frontend.bpu.tage.model.semantic import Base, Branch, Context, Events, Feedback, Hint
from suites.frontend.bpu.tage.monitor.decode import _decode
from suites.frontend.bpu.models.folded_history import PHR_FOLD_LAYOUT


def sparse_context(histories, indices):
    """Restore the configured context with whole-chip-removed folds zeroed."""

    folds = [0] * len(PHR_FOLD_LAYOUT)
    for index, row in zip(indices, histories, strict=True):
        folds[index] = row.foldedHist.as_int()
    return Context(tuple(folds))


def visible_context(context, indices):
    folds = [0] * len(PHR_FOLD_LAYOUT)
    for index in indices:
        folds[index] = context.folds[index]
    return Context(tuple(folds))


def bases_value(lookup):
    # Whole-chip DCE removed cfiPosition and the attribute leaves from the s2
    # MainBTB result. Position is still the public s1 sideband, and base
    # branch kind is training metadata rather than a direction input.
    positions = tuple(value.as_int() for value in lookup.main_btb.s1_positions)
    return tuple(Base(bool(entry.valid.as_int()), positions[slot],
        bool(entry.bits_taken.as_int()), bool(conf.as_int()), 0)
        for slot, (entry, conf) in enumerate(
            zip(lookup.main_btb.result, lookup.main_btb.baseConf, strict=True)))


def hint_value(row):
    provider = bool(row.hasProvider.as_int())
    return Hint(provider, bool(row.hasAlt.as_int()), bool(row.useProvider.as_int()),
        row.providerTableIdx.as_int() if provider else 0, row.providerWayIdx.as_int() if provider else 0,
        row.providerTakenCtr_value.as_int() if provider else 0, row.providerUsefulCtr_value.as_int() if provider else 0,
        bool(row.altOrBasePred.as_int()), bool(row.altConf.as_int()))


def feedback_value(train, *, training_indices):
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
    return Feedback(train.start_pc.as_int(),
                    sparse_context(train.history, training_indices), tuple(branches))


def events_value(sample, lookup_indices, training_indices):
    lookup = sample.lookup
    return Events(lookup.start_pc.as_int(),
        sparse_context(lookup.history, lookup_indices),
        tuple(value.as_int() for value in lookup.main_btb.s1_positions),
        bool(lookup.s0_fire.as_int()), bool(lookup.s1_fire.as_int()),
        feedback_value(sample.train, training_indices=training_indices)
        if sample.train_valid.as_int() else None,
        bool(sample.enabled.as_int()), bool(sample.ready.as_int()), bool(sample.reset.as_int()))


class TageSemanticMonitor:
    def __init__(self, dut, ports):
        self.clock = ports.lookup.clock
        self.inputs = Bundle(reset=dut.reset, enabled=ports.control.bits.enable,
            ready=ports.status.bits.reset_done, lookup=ports.lookup.bits,
            train_valid=ports.training.valid, train=ports.training.bits).compile_sampler()
        self.outputs = Bundle(prediction=ports.prediction.bits, enabled=ports.control.bits.enable,
            bases=ports.lookup.bits, fast=ports.prediction.bits.fast_taken_vec,
            sc=ports.prediction.bits.sc_counter_vec).compile_sampler()
        self.lookup_indices = ports.lookup_history_indices
        self.training_indices = ports.training_history_indices
        self.launched = Events(enabled=False, ready=False)
        self.execution = None
        self.subscriptions = []

    def start(self, execution, checker):
        self.execution = execution
        checker.history_indices = self.lookup_indices

        def inputs(event):
            launched = events_value(self.inputs(), self.lookup_indices, self.training_indices)
            # Reset clears state at the edge it is asserted, before ordinary
            # registered inputs become visible; apply the sampled pin now.
            delivered = self.launched
            if launched.reset and not delivered.reset:
                delivered = replace(delivered, reset=True)
            checker.capture_input(event, delivered)
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
