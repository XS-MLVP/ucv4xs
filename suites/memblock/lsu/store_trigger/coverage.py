"""Semantic functional coverage for MemTrigger_3 (store trigger).

Each bin is a *checked behaviour* from ``docs/contracts/store-trigger.md``: a
concrete expected outcome the test asserted, including negative outcomes such
as "NAPOT is rejected" or "a closed gate suppresses an otherwise matching
address". Bins are declared explicitly so a reader can audit that every
contract clause has a witnessed check.
"""
from __future__ import annotations

from toffee import Bin, CoverGroupDef, CoverPointDef

TRIGGER_CASES = (
    # Scalar matchType behaviour (positive and negative).
    "scalar.eq_hit",
    "scalar.eq_miss",
    "scalar.ge_hit",
    "scalar.ge_miss",
    "scalar.lt_hit",
    "scalar.lt_miss",
    "scalar.napot_rejected",
    # CBO cache-line mode.
    "cbo.line_hit",
    "cbo.line_miss",
    "cbo.ignores_matchtype",
    "cbo.ignores_vector_mode",
    # Vector unit-stride mode.
    "vector.mask_hit",
    "vector.mask_miss",
    "vector.ignores_matchtype",
    # Independent preconditions.
    "gate.select",
    "gate.debug_mode",
    "gate.t_enable",
    "gate.store",
    # chain / timing.
    "chain.start_does_not_fire",
    "chain.continue_fires",
    "chain.broken_by_previous_miss",
    "chain.timing_mismatch",
    "chain.timing_match",
    # Action encoding and priority.
    "action.debug_ignores_bp_exp",
    "action.breakpoint_allowed",
    "action.breakpoint_blocked",
    "action.other_encoding_none",
    "priority.debug_over_breakpoint",
    # Multi-slot independence.
    "multi.slot0_only",
    "multi.slot1_only",
    "multi.slot2_only",
    "multi.slot3_only",
)

GROUP_DEFINITION = CoverGroupDef(
    "mt_case",
    (
        CoverPointDef(
            "case",
            {name: Bin.values(name) for name in TRIGGER_CASES},
            description="store trigger 的可读语义情形：匹配模式、比较类型（含不支持的编码）、"
                        "四类前置条件、chain/timing、action 与优先级、四路独立。",
        ),
    ),
    description="MemTrigger_3 语义情形清单。",
)


class StoreTriggerCoverage:
    def __init__(self) -> None:
        self.cases = GROUP_DEFINITION.instantiate("store_trigger.case")

    def sample_case(self, name: str) -> None:
        if name not in TRIGGER_CASES:
            raise KeyError(f"undeclared trigger cover case: {name}")
        self.cases.sample({"case": name}, details=False)

    def observe(self, **_) -> None:
        """Automatic bins are not used: every bin is an explicitly asserted case."""
