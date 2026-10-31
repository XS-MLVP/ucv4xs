"""CommitQueue checker: independent selective-FIFO reference."""

from __future__ import annotations

from typing import Sequence

from suites.frontend.ftq.oracle import CallRet
from suites.frontend.ftq.oracle import CallRetFifo


class CommitChecker:
    def __init__(self, capacity: int = 64, guard: int = 8) -> None:
        self.model = CallRetFifo(capacity=capacity, guard=guard)

    def step(self, rows: Sequence[CallRet | None]) -> CallRet | None:
        if len(rows) != 8:
            raise ValueError("CommitQueue has eight commit lanes")
        return self.model.step(tuple(rows))

    def check(self, expected: CallRet | None, observed: CallRet | None) -> None:
        assert observed == expected, f"observed {observed}, expected {expected}"

    @property
    def depth(self) -> int:
        return (self.model.enq - self.model.deq) % self.model.capacity
