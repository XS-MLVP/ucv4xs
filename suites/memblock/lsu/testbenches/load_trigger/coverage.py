"""Semantic functional coverage for MemTrigger (load variant)."""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

CASES = (
    "scalar.eq_hit", "scalar.eq_miss", "scalar.ge_hit", "scalar.ge_miss",
    "scalar.lt_hit", "scalar.lt_miss", "scalar.napot_rejected",
    "vector.mask_hit", "vector.mask_miss", "vector.ignores_matchtype",
    "gate.load_bit", "gate.select", "gate.debug_mode", "gate.t_enable",
    "prf.suppresses_scalar", "prf.does_not_suppress_vector",
    "chain.start_does_not_fire", "chain.continue_fires",
    "chain.broken_by_previous_miss", "chain.timing_mismatch",
    "action.debug_ignores_bp_exp", "action.breakpoint_allowed",
    "action.breakpoint_blocked", "action.other_encoding_none",
    "priority.debug_over_breakpoint",
    "multi.slot0_only", "multi.slot1_only", "multi.slot2_only", "multi.slot3_only",
    "cbo.branch_absent",
)
GROUP = CoverGroupDef(
    "lt_case",
    (CoverPointDef("case", {name: Bin.values(name) for name in CASES},
                   description="load trigger 的可读语义情形：标量三比较、向量 mask、四类门控、"
                               "isPrf 只抑制标量路径、chain/timing、action 优先级、四路独立、"
                               "以及缺失的 CBO 分支。"),),
    description="MemTrigger（load）语义情形清单。",
)


class LoadTriggerCoverage:
    def __init__(self) -> None:
        self.cases = GROUP.instantiate("load_trigger.case")

    def sample_case(self, name: str) -> None:
        if name not in CASES:
            raise KeyError(f"undeclared load trigger cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Every bin is an explicitly asserted case."""
