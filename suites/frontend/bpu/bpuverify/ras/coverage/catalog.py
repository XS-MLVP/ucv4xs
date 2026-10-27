"""bpuverify.ras.coverage.catalog components."""

from __future__ import annotations

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.common.env.artifacts import output_path
from pathlib import Path
from typing import Any
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase


def ras_coverage_model():
    return CoverGroupDef(
        "ras_operations",
        (
            CoverPointDef(
                "operation",
                {
                    "push": Bin.values("push"),
                    "pop": Bin.values("pop"),
                    "redirect": Bin.values("redirect"),
                    "disabled_top_held": Bin.values("disabled_top_held"),
                },
            ),
            CoverPointDef(
                "stack_shape",
                {
                    "empty": Bin.values("empty"),
                    "unique": Bin.values("unique"),
                    "repeated": Bin.values("repeated"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ras")


def write_ras_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ras" / "functional-coverage.json"))


def ras_enable_integrity_coverage_model():
    return CoverGroupDef(
        "ras_enable_integrity",
        (
            CoverPointDef(
                "phase",
                {
                    "top_preserved": Bin.values("top_preserved"),
                    "metadata_preserved": Bin.values("metadata_preserved"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ras.enable_integrity")


def write_ras_enable_integrity_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ras" / "functional-coverage-enable-integrity.json"))


def ras_commit_recovery_coverage_model():
    return CoverGroupDef(
        "ras_commit_recovery",
        (
            CoverPointDef(
                "phase",
                {
                    phase: Bin.values(phase)
                    for phase in (
                        "commit_a", "commit_b", "commit_c", "queue_reused",
                        "return_c_to_b", "return_b_to_a", "return_a_to_empty",
                    )
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ras.commit_recovery")


def write_ras_commit_recovery_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ras" / "functional-coverage-commit-recovery.json"))


def ras_repeated_commit_coverage_model():
    return CoverGroupDef(
        "ras_repeated_commit",
        (
            CoverPointDef(
                "phase",
                {
                    phase: Bin.values(phase)
                    for phase in (
                        "normal_pushes", "normal_returns", "normal_empty",
                        "saturated_pushes", "saturated_returns", "saturated_empty",
                    )
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ras.repeated_commit")


def write_ras_repeated_commit_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ras" / "functional-coverage-repeated-commit.json"))


def ras_nested_restore_coverage_model():
    return CoverGroupDef(
        "ras_nested_restore",
        (
            CoverPointDef(
                "phase",
                {
                    phase: Bin.values(phase)
                    for phase in (
                        "push_a", "push_b", "push_c", "restore_b",
                        "pop_b", "pop_a",
                    )
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ras.nested_restore")


def write_ras_nested_restore_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ras" / "functional-coverage-nested-restore.json"))


def ras_overflow_recovery_coverage_model():
    return CoverGroupDef(
        "ras_overflow_recovery",
        (
            CoverPointDef(
                "phase",
                {
                    phase: Bin.values(phase)
                    for phase in (
                        "push_guarded", "pop_guarded", "rollback",
                        "push_resumed", "pop_resumed",
                    )
                },
            ),
        ),
    ).instantiate("kunminghu_v3.ras.overflow_recovery")


def write_ras_overflow_recovery_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "ras" / "functional-coverage-overflow-recovery.json"))
