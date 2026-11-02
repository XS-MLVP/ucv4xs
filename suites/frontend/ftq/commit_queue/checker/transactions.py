"""Input-owned FIFO lifecycle, separate from the public payload reference."""
from collections import deque

from toffee import Scoreboard

from suites.frontend.ftq.commit_queue.checker.model import CommitChecker
from suites.frontend.ftq.commit_queue.transaction.types import OwnedAction, Terminal
from suites.frontend.ftq.oracle import CallRetFifo


class CommitTransactions(CommitChecker):
    def __init__(self):
        super().__init__()
        self.scoreboard = Scoreboard('commit_queue.transactions')
        self.pending = deque()
        self.offered = {}
        self.accepted = {}
        self.terminals = {}
        self.epoch = 0
        self._resetting = False

    def check(self, expected, observed):
        # Keep the public checker API on the same contextual/sticky comparison
        # path as automatic phase checks, not the old standalone bare assert.
        self.scoreboard.check(expected=expected, actual=observed)

    def require_clean(self):
        if self.scoreboard.status.failed:
            raise RuntimeError('commit_queue has a prior comparison failure')

    def terminal(self, action, status, tick):
        if action.uid in self.terminals:
            raise AssertionError('commit_queue duplicate terminal UID')
        self.terminals[action.uid] = Terminal(action, status, tick)

    def advance_slot(self, frame, before, after, tick):
        check = self.scoreboard.check
        # Actual input identity/payload is frozen before the accepting edge.
        check(expected=(frame.reset, frame.rows), actual=(before.reset, before.rows))
        head_before = self.model.mem[self.model.deq]
        # The exported DefaultConfig reset is asynchronous (the closure has
        # posedge clock OR posedge reset), not a synchronous data input. Its
        # first DriveStable snapshot must already show the fixed empty answer.
        check(expected=None if frame.reset else head_before, actual=before.head)
        check(expected=head_before, actual=self.pending[0].value if self.pending else None)
        if frame.reset:
            for action in self.pending:
                self.terminal(action, 'reset-cancelled', tick - 1)
            self.pending.clear()
            self.model = CallRetFifo()
            if not self._resetting:
                self.epoch += 1
            self._resetting = True
            expected = None
        else:
            self._resetting = False
            full = self.depth >= self.model.capacity - self.model.guard
            # The old head is consumed on this edge; the new post-edge head
            # is a preview, not a second completion of the same input UID.
            if self.pending:
                self.terminal(self.pending.popleft(), 'completed', tick)
            for lane, row in enumerate(frame.rows):
                if row is None:
                    continue
                action = OwnedAction((self.epoch, frame.slot, lane), row, tick)
                if action.uid in self.offered:
                    raise AssertionError('commit_queue duplicate offered UID')
                self.offered[action.uid] = action
                if row.ras == 0:
                    self.terminal(action, 'filtered-none', tick)
                elif full:
                    self.terminal(action, 'capacity-rejected', tick)
                else:
                    self.accepted[action.uid] = action
                    self.pending.append(action)
            expected = self.step(frame.rows)
        # Advance the independent reference for the real edge even on mismatch;
        # a swallowed exception must not fictitiously rewind hardware time.
        check(expected=expected, actual=after.head)
        check(expected=expected, actual=self.pending[0].value if self.pending else None)

    def audit(self):
        self.require_clean()
        accepted_terminal = {uid for uid, terminal in self.terminals.items()
                             if terminal.status in {'completed', 'reset-cancelled'}}
        pending = {action.uid for action in self.pending}
        assert not (accepted_terminal & pending), 'commit_queue completed UID still pending'
        assert set(self.accepted) == accepted_terminal | pending, 'commit_queue lost an accepted UID'
        assert set(self.offered) == set(self.terminals) | pending, 'commit_queue lost an offered UID'
        assert self.depth == len(self.pending), 'commit_queue reference/UID depth mismatch'

    def receipt(self):
        self.audit()
        return dict(offered=tuple(self.offered), accepted=tuple(self.accepted),
                    pending=tuple(action.uid for action in self.pending),
                    terminals=tuple(self.terminals.values()))
