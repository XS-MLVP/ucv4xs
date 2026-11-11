"""Input-established identities, actual phase witnesses and storage oracle.

The native rise-write source publishes an offer at one rising snapshot. The
next DriveStable/rising pair proves physical consumption. Functional SRAM data
is present at that latter rising edge; MBIST ack and full-word data are separate
pipeline events. Neither payload equality nor an ack guesses a response UID.
"""
from dataclasses import dataclass, replace
from toffee import CheckContext, Scoreboard, ScoreboardMode
from suites.frontend.icache.testbenches.databank.env.driver.cycle import encode
from suites.frontend.icache.testbenches.databank.model.storage import BankStorage
from suites.frontend.icache.testbenches.databank.transactions.types import BankCycle
from suites.frontend.icache.testbenches.databank.transactions.types import BankObservation
from suites.frontend.icache.testbenches.databank.transactions.types import BankReadData
from suites.frontend.icache.testbenches.databank.transactions.types import BankReadResult
from suites.frontend.icache.testbenches.shared.transactions.sram import SramControls
from suites.frontend.icache.testbenches.databank.model.sram_initialization import SramInitialization
from suites.frontend.icache.testbenches.databank.model.sram_word import KnownWord


@dataclass(frozen=True, slots=True)
class BankInput:
    uid: int
    kind: str
    request: object
    planned_epoch: int
    launch_tick: int
    state: str = 'planned'
    accepted_tick: int | None = None
    ack_tick: int | None = None
    response_tick: int | None = None
    delivery_tick: int | None = None
    terminal_tick: int | None = None
    sources: tuple = ()
    memory_mask: int | None = None
    response_known_mask: int | None = None


class BankTransactions:
    def __init__(self):
        self.board = Scoreboard('databank.input-storage-and-response')
        self.epoch = 0
        self.tick = 0
        self._uid = 0
        self._plans = {}
        self._reset_steps = {}
        self._reset_active = False
        self._wire = {}
        self._rows = {}
        self._results = {}
        self._bist_regs = None
        self._macro = None
        self._bist_due = {}
        self._rdata_due = {}
        self._raw = [None] * 4
        self._rdata = [None] * 4
        self.store = BankStorage()
        self.initialization = SramInitialization(256)
        self._idle_controls = SramControls.idle(4)
        self._controls = self._idle_controls
        self._previous_inputs = self._wire_values(BankCycle(), self._controls)

    @property
    def rows(self):
        return tuple(self._rows.values())

    def check(self, expected, actual, uid=None):
        self.board.check(expected=expected, actual=actual,
            context=CheckContext(self.board.name, ScoreboardMode.DIRECT,
                sequence_id=uid, request=self._rows.get(uid)))

    def plan(self, tick, cycle):
        self.check(False, tick in self._plans)
        uids = {}
        for kind in ('read', 'write', 'bist'):
            request = getattr(cycle, kind)
            if request is not None:
                self._uid += 1
                uids[kind] = self._uid
                self._rows[self._uid] = BankInput(self._uid, kind, request, self.epoch, tick)
        if cycle.controls is not None:
            cycle.controls.require_groups(4)
            self._uid += 1
            uids['controls'] = self._uid
            self._rows[self._uid] = BankInput(self._uid, 'controls', cycle.controls,
                                              self.epoch, tick)
        self._plans[tick] = (cycle, uids)
        return tuple(uids.values())

    def plan_reset(self, start, cycles):
        self._uid += 1
        uid = self._uid
        self._rows[uid] = BankInput(uid, 'reset', cycles, self.epoch, start)
        for index, level in enumerate((1,) * cycles + (0, 0)):
            tick = start + index * 2
            self.check(False, tick in self._reset_steps)
            self._reset_steps[tick] = (level, uid, index == cycles + 1)
        return uid

    def _terminal(self, uid, state, tick, **fields):
        row = self._rows[uid]
        self.check(None, row.terminal_tick, uid)
        self._rows[uid] = replace(row, state=state, terminal_tick=tick, **fields)

    @staticmethod
    def _wire_values(cycle, controls):
        values = encode(cycle)
        return dict(read=(values['read']['valid'], values['read']['setIdx'], values['read']['waymask']),
            write=tuple(values['write'][name] for name in ('valid', 'setIdx', 'waymask', 'data', 'code')),
            bist=tuple(values['bist'][name] for name in
                ('req', 'all', 'array', 'readen', 'writeen', 'be', 'addr', 'addr_rd', 'indata')),
            controls=controls.as_tuples())

    @staticmethod
    def _hold_mask(controls):
        return sum((row[0] << way) for way, row in enumerate(controls))

    def _cancel_current(self, tick):
        current = set(self._wire.values())
        if self._macro is not None:
            current.add(self._macro[0])
        for rows in self._bist_due.values():
            current.update(uid for uid, _ in rows)
        for uid in current:
            if self._rows[uid].terminal_tick is None:
                self._terminal(uid, 'reset-cancelled', tick)
        self._wire = {}
        self._macro = self._bist_regs = None
        self._bist_due.clear()
        self._rdata_due.clear()
        self._raw = [None] * 4
        self._rdata = [None] * 4

    def _functional(self, before, after, tick, macro):
        accepted, results = [], []
        write_uid, read_uid = self._wire.get('write'), self._wire.get('read')
        write_mask = 0
        blocked_read_mask = self._rows[write_uid].request.waymask if write_uid is not None else 0
        hold_mask = self._hold_mask(self._controls.as_tuples())
        control_uid = self._wire.get('controls')
        if control_uid is not None:
            self._terminal(control_uid, 'applied', tick, accepted_tick=tick)
            accepted.append(control_uid)
        if write_uid is not None:
            row = self._rows[write_uid]
            if not before.write_ready:
                self._terminal(write_uid, 'not-accepted', tick)
            else:
                accepted.append(write_uid)
                if macro is None:
                    write_mask = row.request.waymask & ~hold_mask
                    self.store.write(row.request.set_index, write_mask,
                        (row.request.data << 2) | (row.request.code << 1),
                        uid=write_uid, epoch=self.epoch, tick=tick, kind='write')
                state = ('mbist-overridden' if macro else
                         'empty-write' if not row.request.waymask else
                         'held' if write_mask != row.request.waymask else 'written')
                self._terminal(write_uid, state, tick, accepted_tick=tick,
                               memory_mask=None if macro else write_mask)
        if read_uid is not None:
            row = self._rows[read_uid]
            request = row.request
            # The bank's aggregate ready is conservative. Individual unblocked
            # way macros may still read on a rejected offer; no global response
            # credit is manufactured from those speculative per-way effects.
            if macro is None and before.write_ready:
                words = self.store.read(request.set_indices)
                for way in range(4):
                    if request.waymask >> way & 1 and not blocked_read_mask >> way & 1:
                        word = KnownWord(words[way], (1 << 66) - 1
                                         if self.store.known[request.set_indices[way]] >> way & 1 else 0)
                        self._raw[way] = word
                        self._rdata_due.setdefault(tick + 2, []).append((way, word))
            if not before.read_ready:
                self._terminal(read_uid, 'not-accepted', tick)
            elif macro is not None:
                accepted.append(read_uid)
                self._terminal(read_uid, 'mbist-overridden', tick, accepted_tick=tick)
            elif not request.waymask:
                accepted.append(read_uid)
                self._terminal(read_uid, 'empty-read', tick, accepted_tick=tick)
            else:
                accepted.append(read_uid)
                expected = self.store.read(request.set_indices)
                for way in range(4):
                    if request.waymask >> way & 1 and self.store.known_mask(request.set_indices) >> way & 1:
                        self.check((expected[way] >> 2, (expected[way] >> 1) & 1),
                            (after.entries.data[way], after.entries.code[way]), read_uid)
                result = BankReadResult(read_uid, self.epoch, tick, tick, after.entries,
                                        self.store.sources(request.set_indices),
                                        self.store.known_mask(request.set_indices) & request.waymask)
                self._results[read_uid] = result
                self._rows[read_uid] = replace(row, state='sampled', accepted_tick=tick,
                    response_tick=tick, sources=result.sources)
                results.append(result)
        return accepted, results

    def _bist_physical(self, tick, macro, controls):
        if macro is None:
            return
        uid, command = macro
        index = command.addr_rd & 255
        ways = tuple(range(4)) if command.all_arrays else ((command.array - 4,)
                    if 4 <= command.array < 8 else ())
        mask = sum(1 << way for way in ways)
        # A physical one-way SRAM writes whole words; be is an observed but
        # inapplicable byte mask (SramInfo.way=1), not a dropped required mask.
        effective_mask = 0
        if command.writeen:
            effective_mask = mask & ~self._hold_mask(controls)
            self.store.write(index, effective_mask, command.indata, uid=uid, epoch=self.epoch,
                             tick=tick, kind='bist')
            self._rows[uid] = replace(self._rows[uid], memory_mask=effective_mask)
        for way in ways:
            if command.readen:
                if not effective_mask >> way & 1:
                    self._raw[way] = KnownWord(self.store.words[index][way],
                        (1 << 66) - 1 if self.store.known[index] >> way & 1 else 0)
                self._rdata_due.setdefault(tick + 2, []).append((way, self._raw[way]))
        row = self._rows[uid]
        self._rows[uid] = replace(row, accepted_tick=tick)
        selected = command.array - 4 if 4 <= command.array < 8 else None
        if command.readen and (selected is None or not effective_mask >> selected & 1):
            expected = KnownWord(self.store.words[index][selected],
                (1 << 66) - 1 if self.store.known[index] >> selected & 1 else 0) if selected is not None else KnownWord(0, (1 << 66) - 1)
            self._bist_due.setdefault(tick + 2, []).append((uid, expected))
        else:
            self._terminal(uid, 'bist-write' if command.writeen else 'bist-no-data', tick)

    def observe(self, before_transfer, after_transfer):
        before, after = before_transfer.value, after_transfer.value
        tick = after_transfer.event.tick
        self.check(tick - 1, before_transfer.event.tick)
        self.check(self.tick + 2, tick)
        self.tick = tick
        cycle, uids = self._plans.pop(tick, (BankCycle(), {}))
        controls = (self._idle_controls if tick in self._reset_steps else
                    cycle.controls if cycle.controls is not None else self._controls)
        controls.require_groups(4)
        wanted = self._wire_values(cycle, controls)
        for name in ('read', 'write', 'bist'):
            # XData's pre-edge input getter already exposes this queued drive,
            # not the preceding RTL-consumed value. Check the declared current
            # intent here and its committed rising view separately. Consumption
            # identity comes from the retained previous rising offer, not from
            # pretending this input preview is a second hardware acceptance.
            self.check(True, getattr(before, name) in (wanted[name], self._previous_inputs[name]),
                       uids.get(name))
            self.check(wanted[name], getattr(after, name), uids.get(name))
        self.check(wanted['controls'], after.controls, uids.get('controls'))
        self.check(True, before.controls in (wanted['controls'], self._previous_inputs['controls']),
                   uids.get('controls'))
        self.check(after.write_ready & (1 - after.write[0]), after.read_ready)
        reset, reset_uid, last_reset = self._reset_steps.pop(tick, (0, None, False))
        self.check(reset, after.reset, reset_uid)
        self.check(reset, before.reset, reset_uid)
        accepted, results = [], []
        if after.reset:
            if not self._reset_active:
                self.epoch += 1
                self._cancel_current(tick)
                self.initialization.begin(reset_uid, self.epoch)
            self._reset_active = True
            index = self.initialization.edge(1)
            self.store.write(index, 15 & ~self._hold_mask(self._controls.as_tuples()), 0,
                uid=self.initialization.uid, epoch=self.initialization.epoch, tick=tick, kind='reset')
            self.check(0, after.bist_ack)
        else:
            self._reset_active = False
            macro, self._macro = self._macro, None
            index = self.initialization.edge(0)
            if index is not None and macro is None:
                self.store.write(index, 15 & ~self._hold_mask(self._controls.as_tuples()), 0,
                    uid=self.initialization.uid, epoch=self.initialization.epoch, tick=tick, kind='reset')
            accepted, results = self._functional(before, after, tick, macro)
            self._bist_physical(tick, macro, self._controls.as_tuples())
            for way, word in self._rdata_due.pop(tick, ()):
                self._rdata[way] = word
            bist_uid = self._wire.get('bist')
            self.check(int(bist_uid is not None), after.bist_ack, bist_uid)
            if bist_uid is not None:
                row = self._rows[bist_uid]
                self._rows[bist_uid] = replace(row, state='acknowledged', ack_tick=tick)
                command = row.request
                if command.all_arrays or command.array >= 4:
                    self._bist_regs = command
                # Invalid-array leaf stress can retain the previous registered
                # select/operation. Its input UID remains this new req edge.
                effective = self._bist_regs
                if effective is None:
                    self._terminal(bist_uid, 'bist-no-selected-array', tick)
                else:
                    self._macro = (bist_uid, effective)
            selected = (self._bist_regs.array - 4 if self._bist_regs is not None
                        and self._bist_regs.array >= 4 else None)
            expected_out = self._rdata[selected] if selected is not None else KnownWord(0, (1 << 66) - 1)
            if expected_out is not None:
                self.check(*expected_out.checked_pair(after.bist_outdata))
            for uid, expected in self._bist_due.pop(tick, ()):
                command = self._rows[uid].request
                if self._bist_regs is not None and command.array == self._bist_regs.array:
                    self.check(*expected.checked_pair(after.bist_outdata), uid)
                    self._terminal(uid, 'bist-responded', tick, response_tick=tick,
                                   response_known_mask=expected.mask)
                else:
                    self._terminal(uid, 'bist-result-unselected', tick)
        if last_reset:
            self._terminal(reset_uid, 'reset-issued', tick)
        self._controls = controls
        self._previous_inputs = wanted
        self._wire = uids
        for uid in uids.values():
            if self._rows[uid].terminal_tick is None:
                self._rows[uid] = replace(self._rows[uid], state='offered')
        return BankObservation(tick, after.read_ready, after.write_ready, after.entries,
            after.bist_ack, after.bist_outdata, tuple(uids.values()), tuple(accepted), tuple(results))

    def deliver(self, result, entries):
        self.check(True, type(result) is BankReadResult)
        self.check(self._results.get(result.uid), result, result.uid)
        row = self._rows[result.uid]
        self.check('read', row.kind, result.uid)
        self.check(result.values, entries, result.uid)
        if row.delivery_tick is None:
            self._terminal(result.uid, 'responded', result.response_tick,
                           delivery_tick=result.response_tick)

    def quiescent(self):
        return not (self._plans or self._reset_steps or self._wire or self._macro
                    or self._bist_due or self._rdata_due)

    def require_idle_inputs(self):
        self.check({}, self._plans)
        self.check({}, self._reset_steps)
        pending = {key: uid for key, uid in self._wire.items()
                   if key != 'controls' or self._rows[uid].request != self._idle_controls}
        self.check({}, pending)

    def require_idle_controls(self):
        self.check(self._idle_controls, self._controls)

    def finish(self):
        self.check(True, self.quiescent())
        for row in self.rows:
            self.check(True, row.terminal_tick is not None, row.uid)
            if row.kind == 'read' and row.response_tick is not None:
                self.check(row.response_tick, row.delivery_tick, row.uid)
        return self.rows
