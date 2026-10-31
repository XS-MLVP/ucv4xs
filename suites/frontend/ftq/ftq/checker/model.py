"""FTQ checker: circular-pointer contract and training-mask invariant."""

from __future__ import annotations

from suites.frontend.ftq.ftq.monitor.decode import pointers
from suites.frontend.ftq.ftq.transaction.types import TrainingEntry
from suites.frontend.ftq.harness import Dut


def after(left, right) -> bool:
    """CircularQueuePtr ``>`` for (flag, value) pairs."""

    return bool((left.flag ^ right.flag) ^ (left.value > right.value))


def full(left, right) -> bool:
    return left.flag != right.flag and left.value == right.value


def distance(enq, deq) -> int:
    if enq.flag == deq.flag:
        return enq.value - deq.value
    return 64 + enq.value - deq.value


class FtqChecker:
    """Replace stripped XSError assertions with contract-level invariants."""

    def __init__(self) -> None:
        self.edges = 0

    def check_pointers(self, dut: Dut) -> None:
        state = pointers(dut)
        bpu, pf, fetch = state.bpu, state.pf[0], state.fetch[0]
        pnr, commit = state.pnr, state.commit
        problems = []
        if after(fetch, bpu) and not full(bpu, fetch):
            problems.append(f"fetch {fetch} runs ahead of bpu {bpu}")
        if after(pf, bpu) and not full(bpu, pf):
            problems.append(f"pf {pf} runs ahead of bpu {bpu}")
        if after(pnr, bpu) and not full(pnr, bpu):
            problems.append(f"pnr {pnr} runs ahead of bpu {bpu}")
        if not 0 <= distance(bpu, commit) <= 64:
            problems.append(f"commit not behind bpu within one lap: {commit} vs {bpu}")
        if problems:
            raise AssertionError("FTQ pointer invariant violated: " + ", ".join(problems))
        self.edges += 1

    @staticmethod
    def training_mask_ok(training: TrainingEntry) -> bool:
        """No predictor update may follow the first mispredicted branch."""

        seen_mispredict = False
        for branch in training.branches:
            if seen_mispredict:
                return False
            if branch.mispredict:
                seen_mispredict = True
        return True
