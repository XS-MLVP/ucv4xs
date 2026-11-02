"""TOP-015/016: ordered resolve ownership, then cache, then BPU consumption.

The queue contract is the same safe eight-report prefix as the verified leaf;
no public training PC/metadata is used to select an owning input UID.
"""
from collections import deque
from dataclasses import dataclass, field

from suites.frontend.ftq.ftq.transaction.types import TrainingEntry
from suites.frontend.ftq.resolve_queue.transaction.types import Branch


def age_after(left, right):
    return 0 < (left - right) % 128 <= 64


@dataclass(frozen=True, slots=True)
class Report:
    uid: tuple
    identity: int
    pc: int
    branch: Branch
    target_known: bool = True
    ifu: bool = False


@dataclass
class Entry:
    identity: int
    pc: int
    reports: list = field(default_factory=list)
    flushed: bool = False


@dataclass
class Cached:
    entry: Entry
    value: TrainingEntry
    metadata_known: bool
    selected: tuple
    metadata_uid: tuple | None = None


class TrainingPath:
    def __init__(self):
        self.queue = deque()
        self.cache = None
        self.offered, self.accepted, self.terminals = {}, {}, {}
        self.redirects = deque(maxlen=2)
        self.redirect_owner = 0
        self.last_backend = None
        self.response_meta, self.cache_handoffs = {}, []

    @staticmethod
    def reports(frame, receiver, epoch, slot):
        rows = []
        for lane, value in enumerate(frame.resolve):
            if value is not None:
                rows.append(Report((epoch, slot, 'resolve', lane), 64 * value.flag + value.index, value.pc,
                    Branch(((value.pc & 15) + value.offset) % 32, value.target, value.taken,
                           value.mispredict, value.branch_type, value.ras_action)))
        forwarded = receiver.ifu_resolve
        if forwarded is not None:
            value = forwarded.request
            pc = value.pc >> 1
            rows.append(Report(forwarded.uid + ('resolve',), 64 * value.flag + value.index, pc,
                Branch(((pc & 15) + value.offset) % 32,
                    0 if forwarded.target is None else forwarded.target % (1 << 49), value.taken, 1,
                    value.branch_type, value.ras_action), forwarded.target is not None, True))
        return tuple(rows)

    @staticmethod
    def eligible(report):
        branch = report.branch
        return report.ifu or not ((branch.branch_type == 2 and not branch.mispredict) or branch.ras_action == 1)

    def head(self, reports):
        if not self.queue or self.queue[0].flushed:
            return None
        first = self.queue[0]
        if any(self.eligible(report) and report.identity == first.identity for report in reports):
            return None
        return first

    def visible(self, backend, *, reset=False):
        if reset or self.cache is None:
            return None
        if backend is not None and age_after(self.cache.entry.identity, 64 * backend.request.flag + backend.request.index):
            return None
        return self.cache

    def terminal(self, report, status, tick):
        assert report.uid not in self.terminals, 'FTQ duplicate resolve terminal'
        self.terminals[report.uid] = (status, tick)

    def advance(self, frame, reports, receiver, enqueue, metadata, tick, *, meta_uids=None):
        backend = receiver.backend
        owner = None if backend is None else 64 * backend.request.flag + backend.request.index
        if frame.reset:
            for entry in self.queue:
                if not entry.flushed:
                    for report in entry.reports:
                        self.terminal(report, 'reset-cancelled', tick - 1)
            if self.cache is not None:
                for report in self.cache.selected:
                    self.terminal(report, 'reset-cancelled', tick - 1)
            self.queue.clear()
            self.cache = None
            self.redirects.append(owner is not None)
            self.redirect_owner = 0
            self.last_backend = owner
            return
        old_entries = tuple(self.queue)
        head = self.head(reports)
        cache = self.cache
        flush_cache = cache is not None and owner is not None and age_after(cache.entry.identity, owner)
        public_fire = cache is not None and not flush_cache and bool(frame.consumers.train)
        can_handoff = cache is None or public_fire
        handoff = head is not None and can_handoff
        consume = bool(self.queue) and (self.queue[0].flushed or handoff)
        if flush_cache:
            for report in cache.selected:
                self.terminal(report, 'redirect-cancelled-cache', tick)
            self.cache = None
        elif public_fire:
            for report in cache.selected:
                self.terminal(report, 'completed', tick)
                self.response_meta[report.uid] = cache.metadata_uid
            self.cache = None
        if handoff:
            entry = Entry(head.identity, head.pc, list(head.reports))
            doomed = ((owner is not None and age_after(entry.identity, owner))
                      or (self.last_backend is not None and age_after(entry.identity, self.last_backend)))
            if doomed:
                for report in entry.reports:
                    self.terminal(report, 'redirect-cancelled-handoff', tick)
            elif not flush_cache:
                first_bad = min((report.branch.position for report in entry.reports if report.branch.mispredict), default=32)
                selected = tuple(report for report in entry.reports if report.branch.position <= first_bad)
                mask = sum(1 << index for index, report in enumerate(entry.reports) if report in selected)
                for report in entry.reports:
                    if report not in selected:
                        self.terminal(report, 'masked-after-mispredict', tick)
                stored = metadata[entry.identity % 64]
                fields = ({} if stored is None else {key.removeprefix('resolveMeta_'): value
                          for key, value in stored.items() if key.startswith('resolveMeta_')})
                value = TrainingEntry(entry.pc, (entry.pc,) * 3 + (((entry.pc + 16) & ~15) % (1 << 49),),
                    tuple(report.branch for report in selected), fields.get('phr_phrPtr_value', 0),
                    fields.get('commonHR_ghr', 0), fields.get('commonHR_valid', 0), mask, fields)
                meta_uid = None if meta_uids is None else meta_uids[entry.identity % 64]
                self.cache = Cached(entry, value, stored is not None, selected, meta_uid)
                self.cache_handoffs.append((tick, tuple(report.uid for report in selected), meta_uid))
        full = len(old_entries) >= 12
        for report in reports:
            assert report.uid not in self.offered, 'FTQ repeated offered resolve UID'
            self.offered[report.uid] = report
            if not self.eligible(report):
                self.terminal(report, 'backend-filtered', tick)
                continue
            if full:
                self.terminal(report, 'capacity-rejected', tick)
                continue
            entry = next((item for item in self.queue if item.identity == report.identity and not item.flushed), None)
            if entry is None:
                entry = Entry(report.identity, report.pc)
                self.queue.append(entry)
            if len(entry.reports) == 8:
                self.terminal(report, 'branch-capacity-rejected', tick)
                continue
            entry.reports.append(report)
            self.accepted[report.uid] = report
        if owner is not None:
            self.redirect_owner = owner
        for entry in old_entries:
            if consume and entry is old_entries[0]:
                continue
            reason = ('redirect-cancelled-queue' if (owner is not None or any(self.redirects))
                      and age_after(entry.identity, self.redirect_owner)
                      else 'overwrite-cancelled-queue' if enqueue is not None and entry.identity % 64 == enqueue % 64 else None)
            if reason is not None and not entry.flushed:
                entry.flushed = True
                for report in entry.reports:
                    self.terminal(report, reason, tick)
        if consume:
            assert self.queue[0] is old_entries[0]
            self.queue.popleft()
        self.redirects.append(owner is not None)
        self.last_backend = owner

    def audit(self):
        pending = {report.uid for entry in self.queue if not entry.flushed for report in entry.reports}
        if self.cache is not None:
            pending.update(report.uid for report in self.cache.selected)
        accepted_done = {uid for uid, (status, _) in self.terminals.items()
                         if status not in ('backend-filtered', 'capacity-rejected', 'branch-capacity-rejected')}
        assert not (pending & set(self.terminals)), 'FTQ resolve terminal remains pending'
        assert set(self.accepted) == pending | accepted_done, 'FTQ lost accepted resolve ancestry'
        assert set(self.offered) == pending | set(self.terminals), 'FTQ lost offered resolve ancestry'
        assert set(self.response_meta) == {uid for uid, (status, _) in self.terminals.items()
                                            if status == 'completed'}, 'FTQ lost training response metadata association'
        return pending
