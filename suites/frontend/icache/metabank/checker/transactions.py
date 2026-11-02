"""Declared UID and physical-frame checking with separate valid/tag ancestry."""
from dataclasses import dataclass, replace
from toffee import Scoreboard, CheckContext, ScoreboardMode
from suites.frontend.icache.metabank.driver.cycle import encode
from suites.frontend.icache.metabank.model.storage import MetaStorage
from suites.frontend.icache.metabank.transaction.types import MetaBankCycle, MetaReadResult, MetaObservation
from suites.frontend.icache.transactions.sram import SramControls
from suites.frontend.icache.models.sram_initialization import SramInitialization


@dataclass(frozen=True, slots=True)
class MetaInput:
    uid: int
    kind: str
    request: object
    planned_epoch: int
    launch_tick: int
    state: str = 'planned'
    accepted_tick: int | None = None
    memory_tick: int | None = None
    validity_tick: int | None = None
    ack_tick: int | None = None
    response_tick: int | None = None
    delivery_tick: int | None = None
    terminal_tick: int | None = None
    storage_sources: tuple = ()
    validity_sources: tuple = ()
    memory_mask: int | None = None
    response_known_mask: int | None = None


class MetaTransactions:
    def __init__(self):
        self.board = Scoreboard('metabank.input-validity-storage-response')
        self.epoch = self.tick = self._uid = 0
        self._plans, self._reset_steps, self._wire, self._rows = {}, {}, {}, {}
        self._results = {}
        self._reset_active = False
        self._read_index = 0
        self._macro = self._bist_regs = None
        self._bist_due, self._rdata_due = {}, {}
        self._raw, self._rdata = [None, None], [None, None]
        self.store = MetaStorage()
        self.initialization = SramInitialization(128)
        self._idle_controls = SramControls.idle(2)
        self._controls = self._idle_controls
        self._previous_inputs = self._wire_values(MetaBankCycle(), self._controls)

    @property
    def rows(self):
        return tuple(self._rows.values())

    def check(self, expected, actual, uid=None):
        self.board.check(expected=expected, actual=actual,
            context=CheckContext(self.board.name, ScoreboardMode.DIRECT, sequence_id=uid, request=self._rows.get(uid)))

    def plan(self, tick, cycle):
        self.check(False, tick in self._plans)
        uids = {}
        for kind in ('read', 'write', 'flush', 'bist'):
            request = cycle.flush_all if kind == 'flush' else getattr(cycle, kind)
            if request is not None and (kind != 'flush' or request):
                self._uid += 1
                uids[kind] = self._uid
                self._rows[self._uid] = MetaInput(self._uid, kind, request, self.epoch, tick)
        if cycle.controls is not None:
            cycle.controls.require_groups(2)
            self._uid += 1
            uids['controls'] = self._uid
            self._rows[self._uid] = MetaInput(self._uid, 'controls', cycle.controls,
                                               self.epoch, tick)
        self._plans[tick] = (cycle, uids)
        return tuple(uids.values())

    def plan_reset(self, start, cycles):
        self._uid += 1
        uid = self._uid
        self._rows[uid] = MetaInput(uid, 'reset', cycles, self.epoch, start)
        for index, value in enumerate((1,) * cycles + (0, 0)):
            tick = start + index * 2
            self.check(False, tick in self._reset_steps)
            self._reset_steps[tick] = (value, uid, index == cycles + 1)

    def _terminal(self, uid, state, tick, **fields):
        row = self._rows[uid]
        self.check(None, row.terminal_tick, uid)
        self._rows[uid] = replace(row, state=state, terminal_tick=tick, **fields)

    def _cancel_current(self, tick):
        current = set(self._wire.values())
        if self._macro is not None:
            current.add(self._macro[0])
        for records in self._bist_due.values():
            current.update(uid for uid, _ in records)
        for uid in current:
            if self._rows[uid].terminal_tick is None:
                self._terminal(uid, 'reset-cancelled', tick)
        self._wire = {}
        self._macro = self._bist_regs = None
        self._bist_due.clear()
        self._rdata_due.clear()
        self._raw, self._rdata = [None, None], [None, None]

    def compare_ways(self, expected, actual, uid, known_mask=15):
        self.check(4, len(actual), uid)
        for way, (want, got) in enumerate(zip(expected, actual, strict=True)):
            self.check(want.valid, got.valid, uid)
            if want.valid and known_mask >> way & 1:
                self.check(want, got, uid)

    def _functional(self, before, after, tick, macro):
        accepted, results = [], []
        write_uid, read_uid, flush_uid = (self._wire.get(name) for name in ('write', 'read', 'flush'))
        hold_mask = self._hold_mask(self._controls.as_tuples())
        control_uid = self._wire.get('controls')
        if control_uid is not None:
            self._terminal(control_uid, 'applied', tick, accepted_tick=tick)
            accepted.append(control_uid)
        if write_uid is not None:
            request = self._rows[write_uid].request
            # Validity is an independent input-valid effect, not tag SRAM fire.
            # Flush/reset has priority over this effect, not over the SRAM word.
            self.store.validate(request.set_index, request.waymask, uid=write_uid, epoch=self.epoch, tick=tick)
            effective_mask = request.waymask & ~hold_mask
            effective = bool(before.write_ready and macro is None and effective_mask)
            if before.write_ready:
                accepted.append(write_uid)
            if effective:
                word = (request.phy_tag << 33) | (request.maybe_rvc_map << 1) | request.code
                self.store.write(request.set_index, effective_mask, (word,) * 4,
                                 uid=write_uid, epoch=self.epoch, tick=tick, kind='write')
            state = ('validity-only-initialization' if not before.write_ready
                     else 'written' if effective and effective_mask == request.waymask
                     else 'held' if effective_mask != request.waymask and macro is None
                     else 'empty-write' if not request.waymask
                     else 'mbist-overridden' if macro else 'validity-only-initialization')
            self._terminal(write_uid, state, tick, accepted_tick=tick if before.write_ready else None,
                           memory_tick=tick if effective else None,
                           validity_tick=tick if request.waymask and flush_uid is None else None,
                           memory_mask=None if macro else effective_mask if before.write_ready else 0)
        if flush_uid is not None:
            self.store.flush(uid=flush_uid, epoch=self.epoch, tick=tick)
            self._terminal(flush_uid, 'invalidated', tick, validity_tick=tick)
        if read_uid is not None:
            row = self._rows[read_uid]
            index = row.request.set_index
            # The SRAM has no flush input: rejected read/flush combinations can
            # still read tags, while readReqReg/validity ownership must not move.
            if macro is None and before.write_ready and write_uid is None:
                for group in range(2):
                    word = self.store.macro_sample(index, group)
                    self._raw[group] = word
                    self._rdata_due.setdefault(tick + 2, []).append((group, word))
            if not before.read_ready:
                self._terminal(read_uid, 'not-accepted', tick)
            else:
                accepted.append(read_uid)
                self._read_index = index
                if macro is not None:
                    self._terminal(read_uid, 'mbist-overridden', tick, accepted_tick=tick)
                else:
                    self.compare_ways(self.store.read(index), after.entries, read_uid, self.store.known[index])
                    result = MetaReadResult(read_uid, self.epoch, tick, tick, after.entries,
                        tuple(self.store.memory_sources[index]), tuple(self.store.validity_sources[index]),
                        self.store.known[index])
                    self._results[read_uid] = result
                    self._rows[read_uid] = replace(row, state='sampled', accepted_tick=tick, response_tick=tick,
                        storage_sources=result.storage_sources, validity_sources=result.validity_sources)
                    results.append(result)
        return accepted, results

    def _bist_physical(self, tick, macro, controls):
        if macro is None:
            return
        uid, command = macro
        index = command.addr_rd & 127
        groups = (0, 1) if command.all_arrays else (command.array,)
        words = tuple((command.indata >> (69 * (way % 2))) & ((1 << 69) - 1) for way in range(4))
        effective_mask = 0
        if command.writeen:
            mask = sum(command.be << (2 * group) for group in groups)
            effective_mask = mask & ~self._hold_mask(controls)
            self.store.write(index, effective_mask, words, uid=uid, epoch=self.epoch, tick=tick, kind='bist')
            self._rows[uid] = replace(self._rows[uid], memory_mask=effective_mask)
        for group in groups:
            if command.readen:
                if not (effective_mask >> (group * 2)) & 3:
                    self._raw[group] = self.store.macro_sample(index, group)
                self._rdata_due.setdefault(tick + 2, []).append((group, self._raw[group]))
        self._rows[uid] = replace(self._rows[uid], accepted_tick=tick,
                                 memory_tick=tick if effective_mask else None)
        if command.readen and not ((effective_mask >> (command.array * 2)) & 3):
            self._bist_due.setdefault(tick + 2, []).append((uid, self.store.macro_sample(index, command.array)))
        else:
            self._terminal(uid, 'bist-write' if command.writeen else 'bist-no-data', tick)

    @staticmethod
    def _hold_mask(controls):
        # Each metadata SRAM group stores two adjacent ways.
        return sum((row[0] * 3) << (2 * group) for group, row in enumerate(controls))

    @staticmethod
    def _wire_values(cycle, controls):
        values = encode(cycle)
        return dict(read=tuple(values['read'][name] for name in ('valid', 'setIdx')),
            write=tuple(values['write'][name] for name in ('valid', 'setIdx', 'waymask', 'phyTag', 'maybeRvcMap', 'code')),
            flush=cycle.flush_all,
            bist=tuple(values['bist'][name] for name in
                ('req', 'all', 'array', 'readen', 'writeen', 'be', 'addr', 'addr_rd', 'indata')),
             controls=controls.as_tuples())

    def observe(self, before_transfer, after_transfer):
        before, after = before_transfer.value, after_transfer.value
        tick = after_transfer.event.tick
        self.check(tick - 1, before_transfer.event.tick)
        self.check(self.tick + 2, tick)
        self.tick = tick
        cycle, uids = self._plans.pop(tick, (MetaBankCycle(), {}))
        controls = (self._idle_controls if tick in self._reset_steps else
                    cycle.controls if cycle.controls is not None else self._controls)
        controls.require_groups(2)
        wanted = self._wire_values(cycle, controls)
        for name in ('read', 'write', 'flush', 'bist'):
            self.check(True, getattr(before, name) in (wanted[name], self._previous_inputs[name]),
                       uids.get(name))
            self.check(wanted[name], getattr(after, name), uids.get(name))
        self.check(wanted['controls'], after.controls, uids.get('controls'))
        self.check(True, before.controls in (wanted['controls'], self._previous_inputs['controls']),
                   uids.get('controls'))
        self.check(after.write_ready & (1 - after.write[0]) & (1 - after.flush), after.read_ready)
        reset, reset_uid, last_reset = self._reset_steps.pop(tick, (0, None, False))
        self.check(reset, before.reset, reset_uid)
        self.check(reset, after.reset, reset_uid)
        accepted, results = [], []
        if after.reset:
            if not self._reset_active:
                self.epoch += 1
                self._cancel_current(tick)
                self.initialization.begin(reset_uid, self.epoch)
                self.store.reset_validity(uid=reset_uid, epoch=self.epoch, tick=tick)
                self._read_index = 0
            self._reset_active = True
            index = self.initialization.edge(1)
            self.store.write(index, 15 & ~self._hold_mask(self._controls.as_tuples()), (0,) * 4,
                uid=self.initialization.uid, epoch=self.initialization.epoch, tick=tick, kind='reset')
            self.check(0, after.bist_ack)
        else:
            self._reset_active = False
            macro, self._macro = self._macro, None
            index = self.initialization.edge(0)
            if index is not None and macro is None:
                self.store.write(index, 15 & ~self._hold_mask(self._controls.as_tuples()), (0,) * 4,
                    uid=self.initialization.uid, epoch=self.initialization.epoch, tick=tick, kind='reset')
            accepted, results = self._functional(before, after, tick, macro)
            self._bist_physical(tick, macro, self._controls.as_tuples())
            for group, word in self._rdata_due.pop(tick, ()):
                self._rdata[group] = word
            bist_uid = self._wire.get('bist')
            self.check(int(bist_uid is not None), after.bist_ack, bist_uid)
            if bist_uid is not None:
                row = self._rows[bist_uid]
                self._rows[bist_uid] = replace(row, state='acknowledged', ack_tick=tick)
                self._bist_regs = row.request
                self._macro = (bist_uid, row.request)
            if self._bist_regs is not None:
                word = self._rdata[self._bist_regs.array]
                if word is not None:
                    self.check(*word.checked_pair(after.bist_outdata))
            for uid, expected in self._bist_due.pop(tick, ()):
                if self._bist_regs.array == self._rows[uid].request.array:
                    self.check(*expected.checked_pair(after.bist_outdata), uid)
                    self._terminal(uid, 'bist-responded', tick, response_tick=tick,
                                   response_known_mask=expected.mask)
                else:
                    self._terminal(uid, 'bist-result-unselected', tick)
        # Valid bits are a live view of readReqReg, independent of tag rdata.
        self.check(tuple((self.store.valid[self._read_index] >> way) & 1 for way in range(4)),
                   tuple(way.valid for way in after.entries))
        if last_reset:
            self._terminal(reset_uid, 'reset-issued', tick)
        self._controls = controls
        self._previous_inputs = wanted
        self._wire = uids
        for uid in uids.values():
            if self._rows[uid].terminal_tick is None:
                self._rows[uid] = replace(self._rows[uid], state='offered')
        return MetaObservation(tick, after.read_ready, after.write_ready, after.entries,
            after.bist_ack, after.bist_outdata, tuple(uids.values()), tuple(accepted), tuple(results))

    def deliver(self, result, entries):
        self.check(True, type(result) is MetaReadResult)
        self.check(self._results.get(result.uid), result, result.uid)
        self.check('read', self._rows[result.uid].kind, result.uid)
        self.compare_ways(result.values, entries, result.uid)
        if self._rows[result.uid].delivery_tick is None:
            self._terminal(result.uid, 'responded', result.response_tick, delivery_tick=result.response_tick)

    def require_idle_inputs(self):
        for pending in (self._plans, self._reset_steps):
            self.check({}, pending)
        pending = {key: uid for key, uid in self._wire.items()
                   if key != 'controls' or self._rows[uid].request != self._idle_controls}
        self.check({}, pending)

    def require_idle_controls(self):
        self.check(self._idle_controls, self._controls)

    def quiescent(self):
        return not (self._plans or self._reset_steps or self._wire or self._macro or self._bist_due or self._rdata_due)

    def finish(self):
        self.check(True, self.quiescent())
        for row in self.rows:
            self.check(True, row.terminal_tick is not None, row.uid)
            if row.kind == 'read' and row.response_tick is not None:
                self.check(row.response_tick, row.delivery_tick, row.uid)
        return self.rows
