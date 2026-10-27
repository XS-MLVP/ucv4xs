"""bpuverify.ittage.coverage.catalog components."""

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


def ittage_coverage_model():
    return CoverGroupDef(
        "ittage_behavior",
        (
            CoverPointDef("lookup", {"miss": Bin.values("miss"), "hit": Bin.values("hit")}),
            CoverPointDef("target", {
                "none": Bin.values("none"),
                "first": Bin.values("first"),
                "changed": Bin.values("changed"),
            }),
            CoverPointDef("operation", {
                "idle": Bin.values("idle"),
                "allocate": Bin.values("allocate"),
                "update": Bin.values("update"),
            }),
            CoverPointDef("gate", {"enabled": Bin.values(1), "disabled": Bin.values(0)}),
            CoverPointDef("provider", {
                "none": Bin.values("none"),
                "primary": Bin.values("primary"),
                "alternate": Bin.values("alternate"),
            }),
            CoverPointDef("allocation", {
                "available": Bin.values(1),
                "blocked": Bin.values(0),
                "not_applicable": Bin.values("not_applicable"),
            }),
            CoverPointDef("history", {
                "zero": Bin.values("zero"),
                "nonzero": Bin.values("nonzero"),
            }),
            CoverPointDef("training_slot", {
                "none": Bin.values("none"),
                "first": Bin.values("first"),
                "later": Bin.values("later"),
            }),
        ),
    ).instantiate("kunminghu_v3.ittage")


def write_ittage_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ittage" / "functional-coverage.json"))


def ittage_enable_coverage_model():
    return CoverGroupDef(
        "ittage_enable",
        (
            CoverPointDef(
                "phase",
                {
                    "disabled_train_blocked": Bin.values("disabled_train_blocked"),
                    "enabled_train_allocates": Bin.values("enabled_train_allocates"),
                    "disabled_lookup_hidden": Bin.values("disabled_lookup_hidden"),
                    "reenabled_hit_retained": Bin.values("reenabled_hit_retained"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ittage.enable")


def write_ittage_enable_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ittage" / "functional-coverage-enable.json"))


def ittage_training_qualification_coverage_model():
    return CoverGroupDef(
        "ittage_training_qualification",
        (
            CoverPointDef(
                "branch",
                {
                    "invalid_indirect_ignored": Bin.values("invalid_indirect_ignored"),
                    "untaken_indirect_ignored": Bin.values("untaken_indirect_ignored"),
                    "conditional_ignored": Bin.values("conditional_ignored"),
                    "direct_ignored": Bin.values("direct_ignored"),
                    "return_ignored": Bin.values("return_ignored"),
                    "return_and_call_ignored": Bin.values("return_and_call_ignored"),
                    "indirect_allocates": Bin.values("indirect_allocates"),
                    "indirect_call_allocates": Bin.values("indirect_call_allocates"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ittage.training_qualification")


def write_ittage_training_qualification_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ittage" / "functional-coverage-training-qualification.json"))


def ittage_branch_vector_coverage_model():
    return CoverGroupDef(
        "ittage_branch_vector",
        (
            CoverPointDef(
                "selection",
                {
                    "four_prior_conditionals": Bin.values("four_prior_conditionals"),
                    "indirect_call_after_conditionals": Bin.values("indirect_call_after_conditionals"),
                    "return_only_rejected": Bin.values("return_only_rejected"),
                    "valid_after_rejected": Bin.values("valid_after_rejected"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ittage.branch_vector")


def write_ittage_branch_vector_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ittage" / "functional-coverage-branch-vector.json"))


def ittage_region_context_coverage_model():
    phases = ("same_region", "next_region", "previous_region", "interleaved_contexts")
    return CoverGroupDef(
        "ittage_region_context",
        (CoverPointDef("phase", {
            phase: Bin.values(phase) for phase in phases
        }),),
    ).instantiate("kunminghu_v3.ittage.region_context")


def write_ittage_region_context_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ittage" / "functional-coverage-region-context.json"))


def ittage_region_capacity_coverage_model():
    return CoverGroupDef(
        "ittage_region_capacity",
        (
            CoverPointDef("phase", {p: Bin.values(p) for p in ("filled", "full_reuse", "interleaved")}),
            CoverPointDef("region", {f"region_{i}": Bin.values(i) for i in range(16)}),
        ),
        crosses=(CrossDef("phase_by_region", ("phase", "region")),),
    ).instantiate("kunminghu_v3.ittage.region_capacity")


def write_ittage_region_capacity_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ittage" / "functional-coverage-region-capacity.json"))


def ittage_region_replacement_coverage_model():
    return CoverGroupDef(
        "ittage_region_replacement",
        (
            CoverPointDef("touch", {str(i): Bin.values(i) for i in (0, 15)}),
            CoverPointDef("step", {str(i): Bin.values(i) for i in (1, 2)}),
            CoverPointDef("observation", {
                name: Bin.values(name) for name in ("victim_redecoded", "survivor_retained")
            }),
            CoverPointDef("victim_half", {name: Bin.values(name) for name in ("low", "high")}),
        ),
        crosses=(CrossDef("touch_step_observation", ("touch", "step", "observation")),),
    ).instantiate("kunminghu_v3.ittage.region_replacement")


def write_ittage_region_replacement_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ittage" / "functional-coverage-region-replacement.json"))


def ittage_pending_feedback_coverage_model():
    phases = (
        "overlap_resident", "overlap_pending_read", "overlap_drained", "overlap_retrained",
        "serial_drained", "serial_retrained",
    )
    return CoverGroupDef(
        "ittage_pending_feedback",
        (
            CoverPointDef("phase", {p: Bin.values(p) for p in phases}),
            CoverPointDef("mode", {p: Bin.values(p) for p in ("first", "highest")}),
            CoverPointDef("bank", {f"bank_{i}": Bin.values(i) for i in range(2)}),
            CoverPointDef("context", {f"row_{i}": Bin.values(i) for i in range(4)}),
        ),
        crosses=(CrossDef("phase_by_mode_by_bank_by_context", ("phase", "mode", "bank", "context")),),
    ).instantiate("kunminghu_v3.ittage.pending_feedback")


def write_ittage_pending_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ittage" / "functional-coverage-pending-feedback.json"))
