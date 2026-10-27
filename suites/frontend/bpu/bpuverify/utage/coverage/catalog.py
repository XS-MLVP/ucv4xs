"""bpuverify.utage.coverage.catalog components."""

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


def utage_coverage_model():
    return CoverGroupDef(
        "utage_behavior",
        (
            CoverPointDef("lookup", {"miss": Bin.values("miss"), "hit": Bin.values("hit")}),
            CoverPointDef("direction", {"not_taken": Bin.values(0), "taken": Bin.values(1)}),
            CoverPointDef("operation", {
                "idle": Bin.values("idle"),
                "allocate": Bin.values("allocate"),
                "update": Bin.values("update"),
            }),
            CoverPointDef("recovery", {
                "normal": Bin.values("normal"),
                "s2_override": Bin.values("s2_override"),
                "s3_override": Bin.values("s3_override"),
            }),
            CoverPointDef("history", {
                "zero": Bin.values("zero"),
                "nonzero": Bin.values("nonzero"),
            }),
        ),
    ).instantiate("kunminghu_v3.utage")


def write_utage_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "utage" / "functional-coverage.json"))


def utage_enable_coverage_model():
    return CoverGroupDef(
        "utage_enable",
        (
            CoverPointDef(
                "phase",
                {
                    "disabled_train_blocked": Bin.values("disabled_train_blocked"),
                    "enabled_train_allocates": Bin.values("enabled_train_allocates"),
                    "disabled_lookup_held": Bin.values("disabled_lookup_held"),
                    "reenabled_contexts": Bin.values("reenabled_contexts"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.utage.enable")


def write_utage_enable_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "utage" / "functional-coverage-enable.json"))


def utage_later_branch_coverage_model():
    return CoverGroupDef(
        "utage_later_branch",
        (
            CoverPointDef(
                "scenario",
                {
                    "same_direct_ignored": Bin.values("same_direct_ignored"),
                    "same_indirect_ignored": Bin.values("same_indirect_ignored"),
                    "later_direct_base_correct": Bin.values("later_direct_base_correct"),
                    "later_indirect_base_correct": Bin.values("later_indirect_base_correct"),
                    "later_direct_suppresses": Bin.values("later_direct_suppresses"),
                    "later_indirect_suppresses": Bin.values("later_indirect_suppresses"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.utage.later_branch")


def write_utage_later_branch_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "utage" / "functional-coverage-later-branch.json"))


def utage_vector_coverage_model():
    return CoverGroupDef(
        "utage_ahead_btb_vector",
        (
            CoverPointDef(
                "corrected_slot",
                {
                    "slot1": Bin.values(1),
                    "slot2": Bin.values(2),
                    "slot3": Bin.values(3),
                },
            ),
            CoverPointDef("association", {
                "serial": Bin.values("serial"),
                "overlap": Bin.values("overlap"),
            }),
        ),
    ).instantiate("kunminghu_v3.utage.ahead_btb_vector")


def write_utage_vector_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "utage" / "functional-coverage-vector.json"))


def utage_low_tick_coverage_model():
    return CoverGroupDef(
        "utage_low_tick_aging",
        (
            CoverPointDef("outcome", {
                "blocked": Bin.values("blocked"),
                "reopened": Bin.values("reopened"),
                "preserved": Bin.values("preserved"),
            }),
            CoverPointDef("provider", {
                "none": Bin.values("none"),
                "lower": Bin.values("lower"),
                "higher": Bin.values("higher"),
            }),
        ),
    ).instantiate("kunminghu_v3.utage.low_tick_aging")


def write_utage_low_tick_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "utage" / "functional-coverage-low-tick.json"))


def utage_shadow_ring_coverage_model():
    return CoverGroupDef(
        "utage_shadow_ring",
        (
            CoverPointDef("mode", {mode: Bin.values(mode) for mode in ("adjacent", "serial")}),
            CoverPointDef("phase", {phase: Bin.values(phase) for phase in (
                "resident", "same_index_bypass", "ring_wrapped",
            )}),
            CoverPointDef("table", {f"table_{i}": Bin.values(i) for i in range(2)}),
            CoverPointDef("bank", {f"bank_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("row", {f"row_{i}": Bin.values(i) for i in range(8)}),
        ),
        crosses=(CrossDef("mode_phase_table_bank_row", ("mode", "phase", "table", "bank", "row")),),
    ).instantiate("kunminghu_v3.utage.shadow_ring")


def write_utage_shadow_ring_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "utage" / "functional-coverage-shadow-ring.json"))


def utage_shadow_persistence_coverage_model():
    return CoverGroupDef(
        "utage_shadow_persistence",
        (
            CoverPointDef("mode", {mode: Bin.values(mode) for mode in ("adjacent", "serial")}),
            CoverPointDef("phase", {phase: Bin.values(phase) for phase in (
                "before_shadow_eviction", "neighbor_retained", "after_shadow_eviction",
            )}),
            CoverPointDef("table", {f"table_{i}": Bin.values(i) for i in range(2)}),
            CoverPointDef("bank", {f"bank_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("row", {f"row_{i}": Bin.values(i) for i in range(8)}),
        ),
        crosses=(CrossDef("mode_phase_table_bank_row", ("mode", "phase", "table", "bank", "row")),),
    ).instantiate("kunminghu_v3.utage.shadow_persistence")


def write_utage_shadow_persistence_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "utage" / "functional-coverage-shadow-persistence.json"))


def utage_aging_matrix_coverage_model():
    return CoverGroupDef(
        "utage_two_round_useful_aging",
        (
            CoverPointDef("phase", {phase: Bin.values(phase) for phase in (
                "initial_blocked", "first_age_allocation", "first_age_upper_blocked",
                "second_age_allocation", "final_original_preserved",
            )}),
            CoverPointDef("bank", {f"bank_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("strength", {f"useful_{i}": Bin.values(i) for i in (1, 2, 3)}),
        ),
        crosses=(CrossDef("phase_bank_useful", ("phase", "bank", "strength")),),
    ).instantiate("kunminghu_v3.utage.two_round_useful_aging")


def write_utage_aging_matrix_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "utage" / "functional-coverage-aging-matrix.json"))


def utage_long_history_coverage_model():
    return CoverGroupDef(
        "utage_short_alias_long_history",
        (
            CoverPointDef("phase", {phase: Bin.values(phase) for phase in (
                "trained", "a_saturated", "b_saturated", "mixed_pipeline",
            )}),
            CoverPointDef("bank", {f"bank_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("older_bit", {f"bit_{i}": Bin.values(i) for i in (6, 7, 8)}),
            CoverPointDef("context", {name: Bin.values(name) for name in ("a", "b", "lower_only")}),
        ),
        crosses=(CrossDef("phase_bank_bit_context", ("phase", "bank", "older_bit", "context")),),
    ).instantiate("kunminghu_v3.utage.short_alias_long_history")


def write_utage_long_history_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "utage" / "functional-coverage-long-history.json"))


def utage_history_collision_coverage_model():
    return CoverGroupDef(
        "utage_history_hash_collision",
        (
            CoverPointDef("mode", {name: Bin.values(name) for name in ("adjacent", "serial")}),
            CoverPointDef("bank", {f"bank_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("fold_pair", {f"bits_{i}_{i + 9}": Bin.values(i) for i in range(3)}),
            CoverPointDef("phase", {phase: Bin.values(phase) for phase in (
                "trained", "blocked", "first_error_blocked", "freed", "reallocated",
                "b_direction_corrected", "saturated", "late_a", "late_b", "pipelined",
            )}),
            CoverPointDef("context", {name: Bin.values(name) for name in ("a", "b", "neighbor")}),
        ),
        crosses=(CrossDef("mode_bank_pair_phase_context", ("mode", "bank", "fold_pair", "phase", "context")),),
    ).instantiate("kunminghu_v3.utage.history_hash_collision")


def write_utage_history_collision_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "utage" / "functional-coverage-history-collision.json"))
