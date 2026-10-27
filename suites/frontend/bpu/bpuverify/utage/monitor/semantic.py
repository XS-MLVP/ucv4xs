"""Public semantic inputs; sparse read-only useful/counter actual observations."""
import asyncio
from contextlib import suppress

from toffee import Bundle, DriveStable, RisingEdge, on

from bpuverify.common.env.memory_direct import memory_signal, memory_signal_names
from bpuverify.utage.bundle.values import _plain
from bpuverify.utage.model.semantic import Base, Context, Events, Feedback, Source
from bpuverify.utage.monitor.observation import UtageUsefulMonitor
from bpuverify.utage.monitor.decode import _decode


def context_value(histories):
    return Context(tuple(row.foldedHist.as_int() for row in histories))


def decode_feedback(train):
    meta = train.meta
    sources = tuple(Source(bool(slot.valid.as_int()), slot.cfiPosition.as_int(),
        bool(slot.hit.as_int()), slot.tableId.as_int(), slot.takenCtr_value.as_int(),
        bool(slot.predTaken.as_int()), bool(slot.baseTaken.as_int())) for slot in meta.abtbResult)
    return Feedback(train.start_pc.as_int(), context_value(meta.foldedPathHistForTrain_hist),
        tuple(index.as_int() for index in meta.readIndex), sources, train.branch.position.as_int(),
        bool(train.branch.taken.as_int()), train.branch.branch_type.as_int())


def decode_events(row):
    lookup = row.lookup
    bases = bases_value(lookup.ahead_btb.result)
    return Events(read_pc=lookup.start_pc.as_int(), read_context=context_value(lookup.normal_history),
        select=bool(lookup.s0_fire.as_int()), pc=lookup.new_start_pc.as_int(),
        context=context_value(lookup.s1_history),
        positions=tuple(value.as_int() for value in lookup.ahead_btb.fastPositions), bases=bases,
        advance=bool(lookup.s2_fire.as_int()),
        override='s3' if lookup.s3_override.as_int() else 's2' if lookup.s2_override.as_int() else None,
        override_pc=lookup.override_start_pc.as_int(), override_context=context_value(lookup.override_history),
        feedback=decode_feedback(row.train) if row.train_valid.as_int() else None,
        enabled=bool(row.enabled.as_int()), ready=bool(row.ready.as_int()), reset=bool(row.reset.as_int()),
        redirect=bool(row.redirect.as_int()))


def bases_value(entries):
    return tuple(Base(bool(entry.valid.as_int()), entry.bits.cfiPosition.as_int(),
        bool(entry.bits.taken.as_int()), entry.bits.attribute.branchType.as_int(),
        bool(entry.bits.isStrongBias.as_int())) for entry in entries)


class UtageSemanticMonitor:
    def __init__(self, agent):
        dut, ports = agent.dut, agent.ports
        self.clock = dut.clock
        self.inputs = Bundle(reset=dut.reset, enabled=ports.control.bits.enable,
            ready=ports.status.bits.reset_done, redirect=dut.io_redirect, lookup=ports.lookup.bits,
            train_valid=ports.training.valid, train=ports.training.bits).compile_sampler()
        self.outputs = Bundle(prediction=ports.prediction.bits, valid=dut.io_meta_valid).compile_sampler()
        self.bases = Bundle(result=ports.lookup.bits.ahead_btb.result).compile_sampler()
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

        def inputs(event):
            launched = decode_events(self.inputs())
            # Public decoded input receipt, separate from golden model state.
            self.last_inputs = self.launched
            checker.capture_input(event, self.launched)
            if self.launched.reset:
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
            checker.capture_output(event, _decode(row.prediction), bool(row.valid.as_int()),
                                   counters=_plain(self.counters()), useful=useful,
                                   live_bases=bases_value(self.bases().result))

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
