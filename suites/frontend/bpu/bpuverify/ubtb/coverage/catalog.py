"""bpuverify.ubtb.coverage.catalog components."""

from __future__ import annotations

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.common.env.artifacts import output_path
from pathlib import Path
from typing import Any
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef


def ubtb_coverage_model():
    """Functional coverage shared by all pytest MicroBtb scenarios."""

    return CoverGroupDef(
        "ubtb_prediction",
        (
            CoverPointDef(
                "phase",
                {"cold": Bin.values("cold"), "trained": Bin.values("trained")},
            ),
            CoverPointDef(
                "result",
                {"miss": Bin.values("miss"), "hit": Bin.values("hit")},
            ),
            CoverPointDef(
                "branch_type",
                {
                    "conditional": Bin.values(1),
                    "direct": Bin.values(2),
                    "indirect": Bin.values(3),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ubtb")


def ubtb_useful_coverage_model():
    """Observable useful-counter transitions, separate from branch-type bins."""

    return CoverGroupDef(
        "ubtb_usefulness",
        (
            CoverPointDef(
                "transition",
                {
                    name: Bin.values(name)
                    for name in (
                        "strong_hit",
                        "aged_hit",
                        "recovered_hit",
                        "saturated_hit",
                        "invalid_miss",
                        "reallocated_hit",
                    )
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ubtb_usefulness")


def ubtb_enable_coverage_model():
    return CoverGroupDef(
        "ubtb_enable",
        (
            CoverPointDef(
                "phase",
                {
                    "disabled_allocate_blocked": Bin.values("disabled_allocate_blocked"),
                    "enabled_allocate": Bin.values("enabled_allocate"),
                    "disabled_update_blocked": Bin.values("disabled_update_blocked"),
                    "disabled_lookup_hidden": Bin.values("disabled_lookup_hidden"),
                    "reenabled_hit_retained": Bin.values("reenabled_hit_retained"),
                    "enabled_update": Bin.values("enabled_update"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ubtb.enable")


def ubtb_replacement_collision_coverage_model():
    phases = (
        "calibrated_victim", "victim_collision_miss",
        "survivor_collision_hit", "replacement_visible",
    )
    return CoverGroupDef(
        "ubtb_replacement_collision",
        (CoverPointDef("phase", {
            phase: Bin.values(phase) for phase in phases
        }),),
    ).instantiate("kunminghu_v3.ubtb.replacement_collision")


def ubtb_resolve_slot_coverage_model():
    return CoverGroupDef(
        "ubtb_resolve_slots",
        (
            CoverPointDef("slot", {str(slot): Bin.values(slot) for slot in range(8)}),
            CoverPointDef("case", {
                case: Bin.values(case) for case in ("attributes", "conditional_aging")
            }),
        ),
        crosses=(CrossDef("slot_case", ("slot", "case")),),
    ).instantiate("kunminghu_v3.ubtb.resolve_slots")


def ubtb_resolve_arbitration_coverage_model():
    phases = (
        "resolve_priority_distinct_pc", "resolve_priority_same_pc",
        "correct_branch_fast_fallback", "invalid_mispredict_fast_fallback",
        "t0_gated_fast_fallback", "unqualified_resolve_preserves_entry",
        "disabled_sources_blocked", "reenabled_resolve_allocates",
    )
    return CoverGroupDef(
        "ubtb_resolve_arbitration",
        (CoverPointDef("phase", {phase: Bin.values(phase) for phase in phases}),),
    ).instantiate("kunminghu_v3.ubtb.resolve_arbitration")


def ubtb_bypass_recovery_coverage_model():
    phases = (
        "recovery_forwarded", "recovery_counter_three",
        "reinitialized_payload_forwarded", "reinitialized_counter_three",
    )
    return CoverGroupDef(
        "ubtb_bypass_recovery",
        (CoverPointDef("phase", {phase: Bin.values(phase) for phase in phases}),),
    ).instantiate("kunminghu_v3.ubtb.bypass_recovery")


def write_ubtb_resolve_slot_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ubtb" / "functional-coverage-resolve-slots.json"))


def write_ubtb_resolve_arbitration_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ubtb" / "functional-coverage-resolve-arbitration.json"))


def write_ubtb_bypass_recovery_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ubtb" / "functional-coverage-bypass-recovery.json"))


def write_ubtb_replacement_collision_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ubtb" / "functional-coverage-replacement-collision.json"))


def write_ubtb_enable_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ubtb" / "functional-coverage-enable.json"))
