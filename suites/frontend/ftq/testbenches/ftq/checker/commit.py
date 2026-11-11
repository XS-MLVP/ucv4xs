"""TOP-014: input-owned FIFO actions projected through independently stored meta.

The public commit has no FTQ pointer/tag. Input order chooses the owning UID;
the observed action/SSP/TOSW only compare against that ancestor, never choose it.
The selective FIFO algorithm is the existing independent CallRetFifo reference.
"""
from collections import deque
from dataclasses import dataclass

from toffee import Scoreboard

from suites.frontend.ftq.testbenches.commit_queue.checker.model import CommitChecker
from suites.frontend.ftq.testbenches.commit_queue.transactions.types import OwnedAction
from suites.frontend.ftq.testbenches.commit_queue.transactions.types import Terminal
from suites.frontend.ftq.testbenches.ftq.transactions.types import CommitEvent
from suites.frontend.ftq.testbenches.ftq.model import CallRetFifo


@dataclass(frozen=True, slots=True)
class StoredMeta:
    uid: tuple
    identity: tuple
    payload: tuple
    tick: int


class FtqCommits(CommitChecker):
    def __init__(self):
        super().__init__()
        self.scoreboard = Scoreboard('ftq.commit-transactions')
        self.pending = deque()
        self.offered, self.accepted, self.terminals = {}, {}, {}
        self.meta_writes, self.response_meta = {}, {}
        self.metadata = [None] * 64
        self.epoch = 0
        self._resetting = self._ledger_failed = False

    def require_clean(self):
        if self.scoreboard.status.failed or self._ledger_failed:
            raise RuntimeError('FTQ commit has a prior comparison or ledger failure')

    def check(self, expected, observed):
        self.scoreboard.check(expected=expected, actual=observed)

    def check_phase(self, observed, *, reset=False):
        if reset or not self.pending:
            self.scoreboard.check(expected=None, actual=observed)
            return
        action = self.pending[0]
        stored = self.metadata[action.value.ptr]
        self.scoreboard.check(expected=True, actual=observed is not None)
        self.scoreboard.check(expected=action.value.ras, actual=observed.ras_action)
        # This hardware store has NO reset value. Unknown prehistory is not0.
        # A full physical metadata input slot writes zeros for unspecified
        # payload fields, so after such a slot every commit-meta bit is known.
        if stored is not None:
            self.scoreboard.check(expected=CommitEvent(action.value.ras, *stored.payload), actual=observed)

    def terminal(self, action, status, tick):
        assert action.uid not in self.terminals, 'FTQ duplicate commit terminal'
        self.terminals[action.uid] = Terminal(action, status, tick)

    def advance_slot(self, frame, slot, before, after, tick):
        self.require_clean()
        try:
            self._advance_slot(frame, slot, before, after, tick)
        except BaseException:
            self._ledger_failed = True
            raise

    def _advance_slot(self, frame, slot, before, after, tick):
        self.check_phase(before, reset=frame.reset)
        if frame.reset:
            for action in self.pending:
                self.terminal(action, 'reset-cancelled', tick - 1)
            self.pending.clear()
            self.model = CallRetFifo()
            if not self._resetting:
                self.epoch += 1
            self._resetting = True
            # metaQueueCommit is unreset storage, not a reset-to-zero promise.
            # Its known earlier input image and provenance remain valid.
        else:
            self._resetting = False
            full = self.depth >= self.model.capacity - self.model.guard
            if self.pending:
                action = self.pending.popleft()
                stored = self.metadata[action.value.ptr]
                self.response_meta[action.uid] = None if stored is None else stored.uid
                self.terminal(action, 'completed', tick)
            for lane, row in enumerate(frame.callret):
                if row is None:
                    continue
                action = OwnedAction((self.epoch, slot, lane), row, tick)
                assert action.uid not in self.offered, 'FTQ duplicate commit offer'
                self.offered[action.uid] = action
                if not row.ras:
                    self.terminal(action, 'filtered-none', tick)
                elif full:
                    self.terminal(action, 'capacity-rejected', tick)
                else:
                    self.accepted[action.uid] = action
                    self.pending.append(action)
            expected = self.step(frame.callret)
            self.scoreboard.check(expected=expected,
                actual=self.pending[0].value if self.pending else None)
        if frame.meta is not None:
            # The store has no reset; a valid write is an input ancestor even
            # on a reset clock edge. Only the resettable FIFO is cancelled.
            meta = frame.meta
            uid = self.epoch, slot, 'meta'
            assert uid not in self.meta_writes, 'FTQ duplicate metadata write'
            stored = StoredMeta(uid, (meta.flag, meta.index),
                tuple(meta.fields.get('commitMeta_ras_' + key, 0)
                      for key in ('ssp', 'tosw_flag', 'tosw_value')), tick)
            self.meta_writes[uid] = stored
            self.metadata[meta.index] = stored
        self.check_phase(after, reset=frame.reset)

    def audit(self):
        self.require_clean()
        try:
            pending = {action.uid for action in self.pending}
            finished = {uid for uid, terminal in self.terminals.items()
                        if terminal.status in ('completed', 'reset-cancelled')}
            assert not (pending & finished), 'FTQ completed commit remains pending'
            assert set(self.accepted) == pending | finished, 'FTQ lost an accepted commit'
            assert set(self.offered) == pending | set(self.terminals), 'FTQ lost a commit offer'
            assert self.depth == len(self.pending), 'FTQ commit depth/UID mismatch'
            assert set(self.response_meta) == {uid for uid, terminal in self.terminals.items()
                if terminal.status == 'completed'}, 'FTQ lost a completed response metadata association'
            return pending
        except BaseException:
            self._ledger_failed = True
            raise

    def receipt(self):
        pending = self.audit()
        return dict(offered=tuple(self.offered), accepted=tuple(self.accepted),
                    pending=tuple(sorted(pending)), terminals=tuple(self.terminals.values()),
                    metadata=tuple(self.meta_writes.values()), response_meta=tuple(self.response_meta.items()),
                    unknown_metadata=tuple(uid for uid, meta_uid in self.response_meta.items() if meta_uid is None))
