"""Reference model for IfuPerfAnalysis (top-down reason pipeline).

Intent: top-down stall/blame reasons must travel with the fetch pipeline.
The unit keeps three reason snapshots so that a reason injected at the front
is reported three cycles later, in step with the instruction that experienced
it.  Three events can annotate a snapshot:

* an I-cache or I-TLB miss bubble belongs to the stage that waited for the
  memory response;
* an IFU write-back redirect blames a BTB miss for the whole in-flight window;
* a backend redirect overrides the frontend blame with the predictor class
  supplied by the backend (TAGE/ITTAGE/RAS/SC/BTB, or memory-violation/other).

Reasons are replaced from the incoming snapshot, not accumulated: a reason
that is no longer reported must age out exactly when the pipeline stage does.
"""

from __future__ import annotations

from dataclasses import dataclass

WIDTH = 76
STAGES = 3

# TopDownCounters ids used by this unit (zero-based enumeration).
TAGE_MISS = 3
SC_MISS = 4
ITTAGE_MISS = 5
RAS_MISS = 6
MEM_VIO = 7
OTHER_REDIRECT = 8
ICACHE_MISS = 10
ITLB_MISS = 11
BTB_MISS = 12

FTQ_BITS = (2, 3, 5, 6, 7, 8, 9)


@dataclass
class Inputs:
    ftq_bits: int = 0
    icache_miss: int = 0
    itlb_miss: int = 0
    backend_redirect: int = 0
    control_flow_redirect: int = 0
    memory_violation_redirect: int = 0
    tage_miss: int = 0
    ittage_miss: int = 0
    ras_miss: int = 0
    ifu_wb_redirect: int = 0


class PerfModel:
    def __init__(self) -> None:
        self.stages: list[set[int]] = [set(), set(), set()]

    def output(self) -> int:
        return sum(1 << bit for bit in self.stages[2])

    @staticmethod
    def _assign(reasons: set[int], bit: int, value: int) -> None:
        if value:
            reasons.add(bit)
        else:
            reasons.discard(bit)

    def tick(self, inputs: Inputs) -> None:
        stage0 = {bit for bit in FTQ_BITS if (inputs.ftq_bits >> bit) & 1}
        stage1 = set(self.stages[0])
        if inputs.icache_miss:
            stage1.add(ICACHE_MISS)
        if inputs.itlb_miss:
            stage1.add(ITLB_MISS)
        stage2 = set(self.stages[1])
        for reasons in (stage0, stage1, stage2):
            if inputs.backend_redirect:
                if inputs.control_flow_redirect:
                    self._assign(reasons, TAGE_MISS, inputs.tage_miss)
                    self._assign(reasons, SC_MISS, 0)  # SC has no port in this configuration
                    self._assign(reasons, ITTAGE_MISS, inputs.ittage_miss)
                    self._assign(reasons, RAS_MISS, inputs.ras_miss)
                    self._assign(reasons, BTB_MISS, 0)  # BTB has no port from the backend here
                elif inputs.memory_violation_redirect:
                    reasons.add(MEM_VIO)
                else:
                    reasons.add(OTHER_REDIRECT)
            if inputs.ifu_wb_redirect:
                reasons.add(BTB_MISS)
        self.stages = [stage0, stage1, stage2]
