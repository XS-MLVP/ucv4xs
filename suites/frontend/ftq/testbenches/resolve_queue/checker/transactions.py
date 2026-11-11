"""Atomic merge/consume/cancel contract from input-owned report identities.

The queue is a sequence of entries, not an RTL pointer/SRAM transcription.
Each accepted report is retained under the entry opened by a planned input.
Observed indices/data are compared, never used to discover the owning UID.
"""
from collections import deque
from dataclasses import dataclass, field

from toffee import Scoreboard

from suites.frontend.ftq.testbenches.resolve_queue.transactions.cycle import ReportAction
from suites.frontend.ftq.testbenches.resolve_queue.transactions.cycle import ReportTerminal
from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import Branch
from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import Training


@dataclass
class Entry:
    identity: tuple[int, int]
    pc: int
    actions: list = field(default_factory=list)
    flushed: bool = False


def after(left, right):
    return (left[1] > right[1]) if left[0] == right[0] else (left[1] <= right[1])


class ResolveTransactions:
    def __init__(self):
        self.scoreboard = Scoreboard('resolve_queue.transactions')
        self.entries = deque()
        self.offered, self.accepted, self.terminals = {}, {}, {}
        self.epoch = 0
        self._resetting = False
        self._redirects = deque(maxlen=2)
        self._redirect_owner = (0, 0)

    @staticmethod
    def eligible(report, source):
        return source == 3 or not ((report.branch_type == 2 and not report.mispredict) or report.ras_action == 1)

    def effective(self, frame):
        return [(source, report) for source, report in enumerate(frame.reports)
                if report is not None and self.eligible(report, source)]

    def visible(self, frame):
        if frame.reset or not self.entries or self.entries[0].flushed:
            return None
        head = self.entries[0]
        # A same-entry update suppresses the head in that slot, even when the
        # guard rejects additional reports. It cannot train an incomplete set.
        if any((report.flag, report.index) == head.identity for _, report in self.effective(frame)):
            return None
        branches = tuple(Branch(position=((action.report.pc & 15) + action.report.offset) % 32,
            target=action.report.target, taken=action.report.taken, mispredict=action.report.mispredict,
            branch_type=action.report.branch_type, ras_action=action.report.ras_action) for action in head.actions)
        return Training(head.identity[1], head.identity[0], head.pc, branches)

    def terminal(self, action, status, tick):
        if action.uid in self.terminals:
            raise AssertionError('resolve_queue duplicate terminal UID')
        self.terminals[action.uid] = ReportTerminal(action, status, tick)

    def require_clean(self):
        if self.scoreboard.status.failed:
            raise RuntimeError('resolve_queue has a prior comparison failure')

    def advance_slot(self, frame, slot, before, after_snapshot, tick):
        check = self.scoreboard.check
        check(expected=self.visible(frame), actual=before)
        if frame.reset:
            for entry in self.entries:
                if not entry.flushed:
                    for action in entry.actions:
                        self.terminal(action, 'reset-cancelled', tick - 1)
            self.entries.clear()
            self._redirects.clear()
            if not self._resetting:
                self.epoch += 1
            self._resetting = True
        else:
            self._resetting = False
            old_entries = tuple(self.entries)
            full = len(old_entries) >= 12
            head = self.entries[0] if self.entries else None
            consume = head is not None and (head.flushed or (frame.ready and self.visible(frame) is not None))
            if head is not None and consume and not head.flushed:
                for action in head.actions:
                    self.terminal(action, 'completed', tick)
            # Admit in declared backend-lane/IFU priority; the old physical
            # capacity guard is fixed before any same-slot dequeue occurs.
            for source, report in enumerate(frame.reports):
                if report is None:
                    continue
                action = ReportAction((self.epoch, slot, source), report, tick)
                if action.uid in self.offered:
                    raise AssertionError('resolve_queue duplicate offered UID')
                self.offered[action.uid] = action
                if not self.eligible(report, source):
                    self.terminal(action, 'backend-filtered', tick)
                    continue
                if full:
                    self.terminal(action, 'capacity-rejected', tick)
                    continue
                identity = report.flag, report.index
                entry = next((item for item in self.entries if item.identity == identity and not item.flushed), None)
                if entry is None:
                    entry = Entry(identity, report.pc)
                    self.entries.append(entry)
                if len(entry.actions) == 8:
                    # Functional FTQ-RQ-011's safe contract: retain first8,
                    # reject excess. Preserve the two real hardware XFAILs.
                    self.terminal(action, 'branch-capacity-rejected', tick)
                    continue
                # FTQ-RQ-001/003 bind startPc at original entry admission.
                # Later reports append branches; they cannot rename the owner
                # using a new observed/last-source PC.
                entry.actions.append(action)
                self.accepted[action.uid] = action
            if frame.redirect is not None:
                self._redirect_owner = frame.redirect
            redirects_active = frame.redirect is not None or any(self._redirects)
            # Mark only ancestors that existed before this edge. The normal
            # three-slot redirect grace covers subsequently resolved work.
            for entry in old_entries:
                if entry is head and consume:
                    continue
                reason = ('redirect-cancelled' if redirects_active and after(entry.identity, self._redirect_owner)
                          else 'overwrite-cancelled' if frame.enqueue is not None and entry.identity[1] == frame.enqueue
                          else None)
                if reason and not entry.flushed:
                    entry.flushed = True
                    for action in entry.actions:
                        self.terminal(action, reason, tick)
            if consume:
                assert self.entries[0] is head
                self.entries.popleft()
            self._redirects.append(frame.redirect is not None)
        check(expected=self.visible(frame), actual=after_snapshot)

    def audit(self):
        self.require_clean()
        pending = {action.uid for entry in self.entries if not entry.flushed for action in entry.actions}
        finished = {uid for uid, terminal in self.terminals.items() if terminal.status in {
            'completed', 'reset-cancelled', 'redirect-cancelled', 'overwrite-cancelled'}}
        assert not (pending & finished), 'resolve_queue completed UID is pending'
        assert set(self.accepted) == pending | finished, 'resolve_queue lost an accepted report'
        assert set(self.offered) == pending | set(self.terminals), 'resolve_queue lost an offered report'
        return pending

    def receipt(self):
        pending = self.audit()
        return dict(offered=tuple(self.offered), accepted=tuple(self.accepted), pending=tuple(sorted(pending)),
                    terminals=tuple(self.terminals.values()))
