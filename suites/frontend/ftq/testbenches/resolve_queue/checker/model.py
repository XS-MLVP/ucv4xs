"""Semantic checker: compare training entries with the independent merge model.

The checker consumes monitor transactions, never live pins, so a test cannot
pass by reading the same DUT state it is supposed to judge.
"""

from __future__ import annotations

from dataclasses import dataclass

from toffee import Scoreboard

from suites.frontend.ftq.testbenches.ftq.model import ResolveBranch
from suites.frontend.ftq.testbenches.ftq.model import ResolveMergeModel
from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import ResolveReport
from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import Training


@dataclass(frozen=True)
class ExpectedBranch:
    position: int
    target: int
    taken: int
    mispredict: int
    branch_type: int
    ras_action: int


class ResolveChecker:
    """Own the reference ownership state for one ResolveQueue test."""

    def __init__(self, *, capacity: int = 16, guard: int = 4) -> None:
        self.model = ResolveMergeModel(capacity=capacity, guard=guard)
        self.scoreboard = Scoreboard('resolve_queue.reference', compare=self.compare)

    def accepts(self, report: ResolveReport) -> bool:
        return self.model.accepted(report.branch_type, report.mispredict,
                                   report.ras_action)

    def push(self, report: ResolveReport, *, source: str) -> None:
        self.model.push(
            report.index, report.flag, report.pc,
            ResolveBranch(position=report.offset, target=report.target,
                          taken=report.taken, mispredict=report.mispredict,
                          branch_type=report.branch_type,
                          ras_action=report.ras_action, source=source),
            backend=source != "ifu",
        )

    def advance(self, cycles: int = 1) -> None:
        self.model.advance(cycles)

    def redirect(self, index: int, flag: int = 0) -> None:
        self.model.redirect(index, flag)

    def enqueue(self, index: int) -> None:
        self.model.bpu_enqueue(index)

    def pop(self) -> None:
        self.model.pop()

    def head(self) -> Training | None:
        head = self.model.head()
        if head is None:
            return None
        return Training(
            index=head.index,
            flag=head.flag,
            start_pc=head.start_pc,
            branches=tuple(ExpectedBranch(
                position=b.position, target=b.target, taken=b.taken,
                mispredict=b.mispredict, branch_type=b.branch_type,
                ras_action=b.ras_action,
            ) for b in head.branches),
        )

    def check(self, observed: Training | None) -> None:
        self.scoreboard.check(expected=self.head(), actual=observed)

    @staticmethod
    def compare(expected, observed):
        if expected is None:
            assert observed is None, f"training appeared with no owned entry: {observed}"
            return
        assert observed is not None, f"missing training for entry {expected.index}"
        assert (observed.index, observed.flag) == (expected.index, expected.flag), (
            f"identity: observed {observed.flag}:{observed.index}, "
            f"expected {expected.flag}:{expected.index}")
        assert observed.start_pc == expected.start_pc, (
            f"start PC: observed {observed.start_pc:#x}, expected {expected.start_pc:#x}")
        assert len(observed.branches) == len(expected.branches), (
            f"branch count: observed {observed.branches}, expected {expected.branches}")
        assert observed.valid_mask == expected.valid_mask, 'branch valid slots are not the admitted prefix'
        for got, want in zip(observed.branches, expected.branches):
            assert (got.position, got.target, got.taken, got.mispredict,
                    got.branch_type, got.ras_action) == (
                want.position, want.target, want.taken, want.mispredict,
                want.branch_type, want.ras_action), (got, want)

    def room(self, index: int, flag: int = 0) -> int:
        return self.model.room(index, flag)
