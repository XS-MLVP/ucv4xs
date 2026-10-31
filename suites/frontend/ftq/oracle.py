"""Independent reference models for the FTQ queues.

These models are derived from the microarchitectural contract, not from RTL
assignments: CommitQueue is a selective FIFO of call/return actions, and
ResolveQueue merges branch reports by FTQ identity until the entry leaves.
They intentionally do not share code with the drivers or the RTL.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class CallRet:
    ptr: int
    ras: int


class CallRetFifo:
    """Selective FIFO with a 64-entry storage and an 8-entry reserve."""

    def __init__(self, capacity: int = 64, guard: int = 8) -> None:
        if not 0 < guard < capacity:
            raise ValueError("guard must leave usable capacity")
        self.capacity = capacity
        self.guard = guard
        self.mem: list[CallRet | None] = [None] * capacity
        self.enq = 0
        self.deq = 0

    def step(self, rows: tuple[CallRet | None, ...]) -> CallRet | None:
        # The head is visible for the whole cycle and is consumed on the same
        # edge that admits this cycle's call/return lanes.
        head_before = self.mem[self.deq]
        accepted = [row for row in rows if row is not None and row.ras != 0]
        full = (self.enq - self.deq) % self.capacity >= self.capacity - self.guard
        if full:
            accepted = []
        for offset, row in enumerate(accepted):
            self.mem[(self.enq + offset) % self.capacity] = row
        self.enq = (self.enq + len(accepted)) % self.capacity
        if head_before is not None:
            self.mem[self.deq] = None
            self.deq = (self.deq + 1) % self.capacity
        return self.mem[self.deq]


@dataclass(frozen=True)
class ResolveBranch:
    position: int
    target: int
    taken: int
    mispredict: int
    branch_type: int
    ras_action: int
    source: str


@dataclass
class ResolveOwnership:
    index: int
    flag: int
    start_pc: int
    branches: list[ResolveBranch] = field(default_factory=list)
    flushed: bool = False

    def add(self, branch: ResolveBranch) -> bool:
        if len(self.branches) >= 8:
            return False
        self.branches.append(branch)
        return True


def _after(left: tuple[int, int], right: tuple[int, int]) -> bool:
    """CircularQueuePtr ``>`` for the {flag,value} pair."""

    return bool((left[0] ^ right[0]) ^ (left[1] > right[1]))


class ResolveMergeModel:
    """Semantic ResolveQueue with physical slots, guard, and auto-dequeue.

    The reference keeps a 16-slot ring, an enqueue/dequeue pointer and a
    flushed bit per entry.  It is written from the queue contract, not copied
    from RTL: identity is {flag,value}, branch reports merge up to 8 slots,
    redirects/enqueues only revoke training eligibility, and an already
    flushed head is dequeued one entry per cycle without training.
    """

    def __init__(self, capacity: int = 16, guard: int = 4) -> None:
        if not 0 < guard < capacity:
            raise ValueError("guard must leave usable capacity")
        self.capacity = capacity
        self.guard = guard
        self.mem: list[ResolveOwnership | None] = [None] * capacity
        self.enq = 0
        self.deq = 0

    @property
    def depth(self) -> int:
        return (self.enq - self.deq) % self.capacity

    @property
    def full(self) -> bool:
        return self.depth >= self.capacity - self.guard

    def advance(self, cycles: int = 1) -> None:
        for _ in range(cycles):
            entry = self.mem[self.deq]
            if entry is not None and entry.flushed:
                self.mem[self.deq] = None
                self.deq = (self.deq + 1) % self.capacity

    def _slots(self):
        for offset in range(self.depth):
            yield (self.deq + offset) % self.capacity

    def _find(self, index: int, flag: int) -> ResolveOwnership | None:
        for slot in self._slots():
            entry = self.mem[slot]
            if entry is not None and entry.index == index and entry.flag == flag:
                return entry
        return None

    def accepted(self, branch_type: int, mispredict: int, ras_action: int) -> bool:
        """Backend filter: correct direct branches and returns need no update."""

        return not ((branch_type == 2 and mispredict == 0) or ras_action == 1)

    def push(self, index: int, flag: int, pc: int, branch: ResolveBranch,
             *, backend: bool = True) -> None:
        if backend and not self.accepted(branch.branch_type, branch.mispredict,
                                         branch.ras_action):
            return
        if self.full:
            return
        owner = self._find(index, flag)
        if owner is None:
            owner = ResolveOwnership(index, flag, pc)
            self.mem[self.enq] = owner
            self.enq = (self.enq + 1) % self.capacity
        owner.add(branch)

    def _mark_after(self, index: int, flag: int) -> None:
        for slot in self._slots():
            entry = self.mem[slot]
            if entry is not None and _after((entry.flag, entry.index), (flag, index)):
                entry.flushed = True

    def redirect(self, index: int, flag: int = 0) -> None:
        self._mark_after(index, flag)

    def bpu_enqueue(self, index: int) -> None:
        # The RTL compares only the pointer value here, not its lap flag.
        for slot in self._slots():
            entry = self.mem[slot]
            if entry is not None and entry.index == index:
                entry.flushed = True

    def room(self, index: int, flag: int = 0) -> int:
        owner = self._find(index, flag)
        return 8 if owner is None else 8 - len(owner.branches)

    def head(self) -> ResolveOwnership | None:
        entry = self.mem[self.deq]
        if entry is None or entry.flushed:
            return None
        return entry

    def pop(self) -> ResolveOwnership | None:
        head = self.head()
        if head is not None:
            self.mem[self.deq] = None
            self.deq = (self.deq + 1) % self.capacity
        return head
