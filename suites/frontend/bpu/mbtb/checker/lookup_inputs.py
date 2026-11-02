"""Original-input and stage witnesses, beside (not replacing) SDK association.

The SDK owns response-handle matching. This ledger proves that the intended S0
and its declared S1/S2 pulses really reached the wire, including identical PCs
and custom expected callbacks. It never guesses identity from a response value.
"""
from collections import deque
from dataclasses import dataclass, replace

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.mbtb.transaction.types import MbtbLookup
from suites.frontend.bpu.mbtb.transaction.metadata import MetadataOrigin,metadata_origin


@dataclass(frozen=True, slots=True)
class LookupInput:
    uid: int
    request: MbtbLookup
    planned_epoch: int
    input_only: bool = False
    state: str = 'planned'
    launch_tick: int | None = None
    offer_tick: int | None = None
    offer_epoch: int | None = None
    response_tick: int | None = None
    advance_tick: int | None = None
    advance_launch: int | None = None
    consume_tick: int | None = None
    consume_launch: int | None = None
    deferred_scope: int | None = None
    cancelled_at: int | None = None
    terminal_tick: int | None = None
    sample_tick: int | None = None
    delivery_tick: int | None = None


class LookupInputs:
    def __init__(self):
        self._rows = {}
        self._declared = []
        self._pending = deque()
        self._stages = {name: deque() for name in ('advance', 'consume')}
        self._stage_planned = set()
        self._scope_sequence = 0
        self._scope = None
        self._closed_scopes = set()
        self._retained_consumes = []
        self.epoch = 0
        self._reset_active = False
        self.tick = -1
        self.read_uid = self.frame_uid = None
        self.failure = None
        self.board = Scoreboard('mbtb.planned-lookup-input')
        self.source_board = Scoreboard('mbtb.training-source-ancestry')
        self._sources = {}
        # Completed rows and source evidence are retained, but never scanned
        # from a clock callback. Only current windows/unfinished result owners
        # participate in per-edge work, even in long reset-heavy matrices.
        self._due = {}
        self._awaiting_result = set()
        self._result_uids = {}
        self._disposition_uids = {}

    @property
    def rows(self):
        return tuple(self._rows[uid] for uid in self._declared)

    def fail(self, error):
        if self.failure is None:
            self.failure = error

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def _check(self, expected, actual, uid=None):
        self.board.check(expected=expected, actual=actual,
            context=CheckContext(self.board.name, ScoreboardMode.DIRECT,
                sequence_id=uid, request=self._rows.get(uid)))

    def plan(self, uid, request, *, input_only=False):
        self.raise_failure()
        if type(request) is not MbtbLookup or type(input_only) is not bool:
            raise ValueError('MainBTB lookup requires an immutable validated input plan')
        if uid in self._rows:
            raise AssertionError('MainBTB lookup UID was already declared')
        self._rows[uid] = LookupInput(uid, request, self.epoch, input_only)
        self._declared.append(uid)
        self._pending.append(uid)

    def launched(self, uid, tick):
        row = self._rows[uid]
        self._check(None, row.launch_tick, uid)
        self._rows[uid] = replace(row, launch_tick=tick)
        if not row.input_only:
            self._due.setdefault(tick+4,[]).append(uid)

    def cancel_pending(self, uid, tick):
        row = self._rows[uid]
        self._rows[uid] = replace(row, cancelled_at=tick)

    def stage(self, uid, name):
        self.raise_failure()
        if name not in self._stages or (uid, name) in self._stage_planned:
            raise AssertionError('MainBTB stage token must have one declared original UID')
        self._stage_planned.add((uid, name))
        self._stages[name].append(uid)

    def stage_launched(self, uid, name, tick):
        row = self._rows[uid]
        self._check(None, getattr(row, name + '_launch'), uid)
        self._rows[uid] = replace(row, **{name + '_launch': tick})

    def open_cleanup_scope(self):
        if self._scope is not None:
            raise RuntimeError('MainBTB retained cleanup scope is already declared')
        self._scope_sequence += 1
        self._scope = self._scope_sequence

    def defer_consume(self, uid):
        if self._scope is None:
            raise AssertionError('MainBTB S2 withholding requires an explicit cleanup scope')
        self._rows[uid] = replace(self._rows[uid], deferred_scope=self._scope)

    def close_cleanup_scope(self):
        if self._scope is None:
            raise AssertionError('MainBTB retained cleanup scope was not declared')
        self._closed_scopes.add(self._scope)
        self._scope = None

    def observe(self, tick, events):
        """Consume the saved physical rising-edge input, never a live preview."""
        self.raise_failure()
        try:
            self._check(True, tick > self.tick)
            self.tick = tick
            for uid in tuple(self._pending):
                row = self._rows[uid]
                if row.cancelled_at is not None and tick > row.cancelled_at:
                    self._pending.remove(uid)
                    self._rows[uid] = replace(row, state='cancelled-before-offer', terminal_tick=tick)
            if events.reset and not self._reset_active:
                self.epoch += 1
                self.read_uid = self.frame_uid = None
                for uid in tuple(self._awaiting_result):
                    row=self._rows[uid]
                    if row.state == 'accepted' and row.response_tick is None:
                        self._rows[uid] = replace(row, state='reset-cancelled', terminal_tick=tick)
                self._awaiting_result.clear()
            self._reset_active = events.reset
            previous_read, previous_frame = self.read_uid, self.frame_uid
            self._check((False, (False, False)), (events.last_stage, events.victim_taken))
            if events.select:
                self._check(True, bool(self._pending))
                uid = self._pending[0]
                row = self._rows[uid]
                self._check(row.request.pc, events.pc, uid)
                # Driver acceptance and physical offer are distinct evidence.
                # Their clocks must agree; a later identical beat cannot stand
                # in for a withdrawn/lost earlier input.
                if row.launch_tick is not None:
                    self._check(row.launch_tick, tick, uid)
                self._pending.popleft()
                state = ('reset-filtered' if events.reset else 'initialization-filtered' if not events.ready
                    else 'disabled-filtered' if not events.enabled else 'accepted')
                self._rows[uid] = replace(row, state=state, offer_tick=tick, offer_epoch=self.epoch,
                    terminal_tick=None if state=='accepted' else tick)
                if state == 'accepted':
                    self.read_uid = uid
                    self._awaiting_result.add(uid)
            for name, active, owner in (('advance', events.advance, previous_read),
                                        ('consume', events.consume, previous_frame)):
                if not active:
                    continue
                queue = self._stages[name]
                if name == 'consume' and self._scope is not None and (not queue or queue[0] != owner):
                    # This explicit UT scope drives a retained S2 level, not a
                    # new lookup. Preserve its original frame UID and tick; it
                    # never completes a different input's stage obligation.
                    self._retained_consumes.append((self._scope, tick, owner))
                    continue
                self._check(True, bool(queue))
                uid = queue.popleft()
                row = self._rows[uid]
                self._check(None, getattr(row, name + '_tick'), uid)
                if not events.reset and events.ready and events.enabled and row.state == 'accepted':
                    self._check(uid, owner, uid)
                    if name == 'advance':
                        self.frame_uid = uid
                elif name=='advance' and row.state=='accepted':
                    reason=('reset-cancelled' if events.reset else
                        'initialization-before-result' if not events.ready else 'disabled-before-result')
                    row=replace(row,state=reason,terminal_tick=tick)
                    self._awaiting_result.discard(uid)
                self._rows[uid] = replace(row, **{name + '_tick': tick})
                if name=='advance' and row.input_only and row.state=='accepted':
                    self._due.setdefault(tick+2,[]).append(uid)
        except Exception as error:
            self.fail(error)
            raise

    def observe_output(self, tick):
        """Witness ownership at SDK windows, without consuming its monitor."""
        self.raise_failure()
        try:
            self._check((),tuple(sorted(due for due in self._due if due<tick)))
            for uid in self._due.pop(tick,()):
                row=self._rows[uid]
                self._check(None,row.sample_tick,uid)
                self._check(True, row.offer_tick is not None, uid)
                if row.state == 'accepted':
                    self._check(uid, self.frame_uid, uid)
                    self._rows[uid] = replace(row, response_tick=tick, terminal_tick=tick,sample_tick=tick)
                    self._result_uids.setdefault(tick,[]).append(uid)
                    self._awaiting_result.discard(uid)
                else:
                    self._check(True,row.terminal_tick is not None,uid)
                    self._rows[uid] = replace(row,sample_tick=tick)
                    self._disposition_uids.setdefault(tick,[]).append(uid)
        except Exception as error:
            self.fail(error)
            raise

    def finish(self):
        self.raise_failure()
        self._check((), tuple(self._pending))
        self._check({'advance': (), 'consume': ()}, {name: tuple(ids) for name, ids in self._stages.items()})
        self._check(None, self._scope)
        self._check({},self._due)
        self._check(set(),self._awaiting_result)
        self._check(len(self._declared), len(set(self._declared)))
        self._check(set(self._declared), set(self._rows))
        for row in self.rows:
            if row.state == 'cancelled-before-offer':
                self._check((None, None, None, None), (row.offer_tick, row.response_tick, row.launch_tick,row.delivery_tick), row.uid)
                continue
            self._check(row.launch_tick, row.offer_tick, row.uid)
            self._check(True, row.offer_tick is not None, row.uid)
            if not row.input_only:
                self._check(row.sample_tick,row.delivery_tick,row.uid)
                self._check(True,row.delivery_tick is not None,row.uid)
            if row.state=='accepted':
                self._check(True,row.response_tick is not None,row.uid)
            else:
                self._check(None,row.response_tick,row.uid)
            self._check(True,row.terminal_tick is not None,row.uid)
            if row.state != 'reset-cancelled':
                self._check(True, row.advance_tick is not None, row.uid)
            for name in ('advance', 'consume'):
                sampled, launched = getattr(row, name + '_tick'), getattr(row, name + '_launch')
                self._check(launched, sampled, row.uid)
            self._check(True, row.consume_tick is not None or row.state == 'reset-cancelled'
                or row.deferred_scope in self._closed_scopes, row.uid)
        return self.rows

    def receipt(self):
        return tuple(dict(uid=row.uid, pc=row.request.pc, planned_epoch=row.planned_epoch,
            offer_epoch=row.offer_epoch, launch_tick=row.launch_tick, offer_tick=row.offer_tick,
            response_tick=row.response_tick, advance_tick=row.advance_tick, consume_tick=row.consume_tick,
            sample_tick=row.sample_tick,delivery_tick=row.delivery_tick,
            input_only=row.input_only, state=('responded' if row.state == 'accepted' and row.response_tick is not None else row.state),
            consume_disposition=('physical-pulse' if row.consume_tick is not None else
                'not-offered-in-explicit-scope' if row.deferred_scope is not None else 'not-offered'),
            deferred_scope=row.deferred_scope, terminal_tick=row.terminal_tick) for row in self.rows)

    def source_at(self,tick):
        if self.failure is not None:return None
        candidates=self._result_uids.get(tick,())
        if not candidates:return None
        self._check(1,len(candidates))
        row=self._rows[candidates[0]]
        return MetadataOrigin(row.uid,row.offer_epoch,row.request.pc,row.offer_tick,row.response_tick)

    def disposition_at(self,tick):
        if self.failure is not None:return None
        candidates=self._disposition_uids.get(tick,())
        if not candidates:return None
        self._check(1,len(candidates))
        return self._rows[candidates[0]]

    def delivery_expected(self,uid,tick,*,disposition):
        self.raise_failure()
        row=self._rows[uid]
        self._check(False,row.input_only,uid)
        self._check(row.sample_tick,tick,uid)
        self._check(None,row.delivery_tick,uid)
        if disposition:
            self._check(False,row.state in ('planned','accepted','cancelled-before-offer'),uid)
            return dict(uid=uid,reason=row.state,epoch=row.offer_epoch,offer_tick=row.offer_tick,
                terminal_tick=row.terminal_tick,delivery_tick=row.sample_tick)
        self._check('accepted',row.state,uid)
        self._check(row.response_tick,tick,uid)

    def delivered(self,uid,tick):
        row=self._rows[uid]
        self._check(None,row.delivery_tick,uid)
        self._check(row.sample_tick,tick,uid)
        self._rows[uid]=replace(row,delivery_tick=tick)

    def register_source(self,origin,metadata):
        if origin.uid in self._sources:
            self._check(self._sources[origin.uid],(origin,metadata),origin.uid)
        else:
            self._sources[origin.uid]=(origin,metadata)

    def validate_training_source(self,transaction):
        """Check ancestry only. Branch outcome/target oracle remains independent."""
        self.raise_failure()
        origin=metadata_origin(transaction.meta_entries)
        if origin is None:return
        known=self._sources.get(origin.uid)
        context=CheckContext(self.source_board.name,ScoreboardMode.DIRECT,
            sequence_id=origin.uid,request=dict(source=origin,input=transaction))
        def check(expected,actual):
            self.source_board.check(expected=expected,actual=actual,context=context)
        check(True,known is not None)
        original,metadata=known
        check(original,origin)
        check(self.epoch,origin.epoch)
        check(origin.pc % (1<<49),transaction.pc)
        check(tuple(tuple(source for source in row[:len(proposed)])
            for row,proposed in zip(metadata,transaction.meta_entries,strict=True)),transaction.meta_entries)
