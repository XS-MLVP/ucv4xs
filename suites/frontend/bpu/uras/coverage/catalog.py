"""suites.frontend.bpu.uras.coverage.catalog components."""

from __future__ import annotations

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.runtime.artifacts import output_path
from pathlib import Path
from typing import Any
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef


def uras_coverage_model():
    return CoverGroupDef(
        "uras_paths",
        (
            CoverPointDef(
                "source",
                {
                    "s1": Bin.values("s1"),
                    "s2_override": Bin.values("s2_override"),
                    "s3_override": Bin.values("s3_override"),
                    "s2_advance": Bin.values("s2_advance"),
                    "s3_clear": Bin.values("s3_clear"),
                    "s2_neutral_s3_push": Bin.values("s2_neutral_s3_push"),
                    "s2_pop_s3_push": Bin.values("s2_pop_s3_push"),
                    "s1_pop_s3_push": Bin.values("s1_pop_s3_push"),
                    "s3_pop_s1_neutral": Bin.values("s3_pop_s1_neutral"),
                    "s3_pop_s2_neutral": Bin.values("s3_pop_s2_neutral"),
                    "s2_push_s3_pop": Bin.values("s2_push_s3_pop"),
                    "main_ras": Bin.values("main_ras"),
                    "redirect": Bin.values("redirect"),
                },
            ),
            CoverPointDef("result", {"usable": Bin.values(1), "invalid": Bin.values(0)}),
            CoverPointDef(
                "action",
                {"none": Bin.values(0), "pop": Bin.values(1), "push": Bin.values(2)},
            ),
        ),
    ).instantiate("kunminghu_v3.uras")


def write_uras_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "uras" / "functional-coverage.json"))


def uras_pending_s2_coverage_model():
    """S1 action crossed with the pending S2 operation, after assertions."""

    return CoverGroupDef(
        "uras_pending_s2_priority",
        (
            CoverPointDef("pairing", {
                "push_pop": Bin.values("push_pop"),
                "push_neutral": Bin.values("push_neutral"),
                "pop_pop": Bin.values("pop_pop"),
                "pop_neutral": Bin.values("pop_neutral"),
            }),
            CoverPointDef("usable", {
                "invalid": Bin.values(0),
                "valid": Bin.values(1),
            }),
        ),
    ).instantiate("kunminghu_v3.uras.pending_s2_priority")


def write_uras_pending_s2_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "uras" / "functional-coverage-pending-s2.json"))


def uras_neutral_override_coverage_model():
    """Main-RAS fallback and redirect semantics after neutral correction."""

    return CoverGroupDef(
        "uras_neutral_override",
        (
            CoverPointDef("stage", {str(stage): Bin.values(stage) for stage in (2, 3)}),
            CoverPointDef("phase", {name: Bin.values(name) for name in (
                "quiescent", "cancel_call", "redirect_priority",
                "redirect_recovery", "stable_next",
            )}),
        ),
        crosses=(CrossDef("stage_phase", ("stage", "phase")),),
    ).instantiate("kunminghu_v3.uras.neutral_override")


def write_uras_neutral_override_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "uras" / "functional-coverage-neutral-override.json"))
