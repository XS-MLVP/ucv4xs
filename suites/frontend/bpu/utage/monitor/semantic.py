"""Public semantic inputs; sparse read-only useful/counter actual observations."""
import asyncio
from contextlib import suppress
from dataclasses import replace

from toffee import Bundle, DriveStable, RisingEdge, on

from suites.frontend.bpu.runtime.memory_direct import memory_signal, memory_signal_names
from suites.frontend.bpu.utage.bundle.values import _plain
from suites.frontend.bpu.utage.model.semantic import Base, Context, Events, Feedback, Source
from suites.frontend.bpu.models.folded_history import PHR_FOLD_LAYOUT
from suites.frontend.bpu.utage.monitor.observation import UtageUsefulMonitor
from suites.frontend.bpu.utage.monitor.decode import _decode


def context_value(histories):
    return Context(tuple(row.foldedHist.as_int() for row in histories))


def sparse_context(histories, indices):
    """Place sparse folded-history rows back into the 33-fold context."""

    folds = [0] * len(PHR_FOLD_LAYOUT)
    for index, row in zip(indices, histories, strict=True):
        folds[index] = row.foldedHist.as_int()
    return Context(tuple(folds))


def decode_feedback(train, training_indices):
    meta = train.meta
    sources = tuple(Source(bool(slot.valid.as_int()), slot.cfiPosition.as_int(),
        bool(slot.hit.as_int()), slot.tableId.as_int(), slot.takenCtr_value.as_int(),
        bool(slot.predTaken.as_int()), bool(slot.baseTaken.as_int())) for slot in meta.abtbResult)
    return Feedback(train.start_pc.as_int(),
        context_value(meta.foldedPathHistForTrain_hist),
        tuple(index.as_int() for index in meta.readIndex), sources, train.branch.position.as_int(),
        bool(train.branch.taken.as_int()), train.branch.branch_type.as_int())


def decode_events(row, indices):
    training_indices, normal_indices, s1_indices, override_indices = indices
    lookup = row.lookup
    positions = tuple(value.as_int() for value in lookup.ahead_btb.fastPositions)
    bases = bases_value(lookup.ahead_btb.result, positions)
    return Events(read_pc=lookup.start_pc.as_int(),
        read_context=sparse_context(lookup.normal_history, normal_indices),
        select=bool(lookup.s0_fire.as_int()), pc=lookup.new_start_pc.as_int(),
        context=sparse_context(lookup.s1_history, s1_indices),
        positions=positions, bases=bases,
        advance=bool(lookup.s2_fire.as_int()),
        override='s3' if lookup.s3_override.as_int() else 's2' if lookup.s2_override.as_int() else None,
        override_pc=lookup.override_start_pc.as_int(),
        override_context=sparse_context(lookup.override_history, override_indices),
        feedback=decode_feedback(row.train, training_indices) if row.train_valid.as_int() else None,
        enabled=bool(row.enabled.as_int()), ready=bool(row.ready.as_int()), reset=bool(row.reset.as_int()),
        redirect=bool(row.redirect.as_int()))


def bases_value(entries, positions):
    # Whole-chip DCE removed the ABTB sideband's cfiPosition and strength
    # leaves: the position sideband is the separate fastPositions vector and
    # MicroTage no longer consumes a strong-bias bit. Direction is still the
    # public taken leaf.
    return tuple(Base(bool(entry.valid.as_int()), positions[index],
        bool(entry.bits.taken.as_int()), entry.bits.attribute_branchType.as_int(), False)
        for index, entry in enumerate(entries))


class UtageSemanticMonitor:
    def __init__(self, agent):
        dut, ports = agent.dut, agent.ports
        self.clock = dut.clock
        self.inputs = Bundle(reset=dut.reset, enabled=ports.control.bits.enable,
            ready=ports.status.bits.reset_done, redirect=dut.io_redirect, lookup=ports.lookup.bits,
            train_valid=ports.training_observation.valid,
            train=ports.training_observation.bits).compile_sampler()
        # Whole-chip DCE removed io.meta.valid because the parent consumes
        # only the metadata payload. Metadata is meaningful exactly when the
        # public prediction reports a hit (the reference's own definition).
        self.outputs = Bundle(prediction=ports.prediction.bits).compile_sampler()
        self.bases = Bundle(result=ports.lookup.bits.ahead_btb.result,
                            fastPositions=ports.lookup.bits.ahead_btb.fastPositions).compile_sampler()
        self.training_indices = agent.ports.training_history_indices
        self.history_indices = (
            self.training_indices,
            agent.ports.normal_history_indices,
            agent.ports.s1_history_indices,
            agent.ports.override_history_indices,
        )
        _, cells, _ = UtageUsefulMonitor._bind(agent)
        self.useful = tuple(Bundle(counter=signal).compile_sampler() for signal in cells.counters)
        names = tuple(memory_signal_names(dut))
        counters = {}
        for key, field in (('low', 'lowTickCounter'), ('high', 'highTickCounter')):
            matches = [name for name in names if name.endswith(f'.MicroTage.{field}')]
            if not matches and key == 'high':
                # The two-table build has no high-tick aging consumer. An
                # eliminated private register is not a reason to enable VPI.
                continue
            if len(matches) != 1:
                raise RuntimeError(f'UTAGE memory-direct {field} binding must be unique')
            counters[key] = memory_signal(dut, matches[0].split('.', 1)[1])
        self.counters = Bundle(**counters).compile_sampler()
        self.counter_fields = tuple(counters)
        self.reset_pending = True
        self.launched = Events(enabled=False, ready=False)
        self.last_inputs = None
        self.execution = None
        self.subscriptions = []

    def start(self, execution, checker):
        self.execution = execution
        checker.counter_fields = self.counter_fields
        checker.training_history_indices = self.training_indices

        def inputs(event):
            launched = decode_events(self.inputs(), self.history_indices)
            # Public decoded input receipt, separate from golden model state.
            self.last_inputs = self.launched
            # Reset clears state at the edge it is asserted, while ordinary
            # inputs only affect registered outputs one edge later. Applying
            # the sampled reset immediately keeps the reference's cleared
            # state aligned with the first reset output boundary.
            delivered = self.launched
            if launched.reset and not delivered.reset:
                delivered = replace(delivered, reset=True)
            checker.capture_input(event, delivered)
            if launched.reset:
                self.reset_pending = True
            self.launched = launched

        def outputs(event):
            row = self.outputs()
            wanted = ()
            if checker.initialized and checker.failure is None and checker.events.ready:
                dense = self.reset_pending or checker.model.aged
                wanted = tuple((table, index) for table in range(2) for index in range(512)) if dense else tuple(
                    dict.fromkeys((*checker.model.checked_indices,
                                   *((table, index) for table, index, *_ in checker.model.effects))))
                self.reset_pending = False
            useful = {(table, index): self.useful[table * 512 + index]().counter.as_int()
                      for table, index in wanted}
            sideband = self.bases()
            live_bases = bases_value(
                sideband.result,
                tuple(value.as_int() for value in sideband.fastPositions))
            meta_valid = int(any(value.as_int() for value in row.prediction.hits))
            checker.capture_output(event,
                _decode(row.prediction, self.training_indices), meta_valid,
                                   counters=_plain(self.counters()), useful=useful,
                                   live_bases=live_bases)

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

    def read_useful(self, table, index):
        if type(table) is not int or table not in (0, 1) or type(index) is not int or not 0 <= index < 512:
            raise ValueError('UTAGE useful observation needs a valid table and nine-bit index')
        return self.useful[table * 512 + index]().counter.as_int()
