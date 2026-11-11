"""FTQ transport harness: the pointer contract the design declares as XSError.

The generated RTL strips those assertions (no ``$fatal`` remains), so this
passive post-edge check replaces them for pointer ownership.  It mirrors the
same circular-pointer comparisons and full-queue suppression, so a wrap cannot
be mistaken for a violation.  The FTQ agent also registers an
``InvariantMonitor`` over the same contract; this transport-level check keeps
the guard active even when a test does not start an agent.
"""

from __future__ import annotations

from suites.frontend.ftq.testbenches.shared.env.harness import Dut


class FtqDutHarness(Dut):
    """Shared execution harness plus the FTQ-only pointer safety net."""

    def _owner(self, name: str, index: int = 0) -> tuple[int, int]:
        base = f"FtqDut_top.Ftq.{name}_ptrs_{index}"
        return (self.internal(base + "_flag"), self.internal(base + "_value"))

    @staticmethod
    def _after(left: tuple[int, int], right: tuple[int, int]) -> bool:
        """CircularQueuePtr ``>``: flag xor value-compare (not a 7-bit key)."""

        return bool((left[0] ^ right[0]) ^ (left[1] > right[1]))

    @staticmethod
    def _full(left: tuple[int, int], right: tuple[int, int]) -> bool:
        return left[0] != right[0] and left[1] == right[1]

    @staticmethod
    def _distance(enq: tuple[int, int], deq: tuple[int, int]) -> int:
        if enq[0] == deq[0]:
            return enq[1] - deq[1]
        return 64 + enq[1] - deq[1]

    def check_invariants(self) -> None:
        bpu = self._owner("bpuPtr")
        pf = self._owner("pfPtr")
        fetch = self._owner("fetchPtr")
        commit = self._owner("commitPtr")
        pnr = self._owner("pnrPtr")
        problems = []
        if self._after(fetch, bpu) and not self._full(bpu, fetch):
            problems.append(f"fetch {fetch} runs ahead of bpu {bpu}")
        if self._after(pf, bpu) and not self._full(bpu, pf):
            problems.append(f"pf {pf} runs ahead of bpu {bpu}")
        if self._after(pnr, bpu) and not self._full(pnr, bpu):
            problems.append(f"pnr {pnr} runs ahead of bpu {bpu}")
        distance = self._distance(bpu, commit)
        if not 0 <= distance <= 64:
            problems.append(f"commit is not behind bpu within one lap: {commit} vs {bpu}")
        if problems:
            raise AssertionError("FTQ pointer invariant violated: " + ", ".join(problems))
