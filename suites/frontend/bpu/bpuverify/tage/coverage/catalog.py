"""bpuverify.tage.coverage.catalog components."""

from __future__ import annotations
from bpuverify.common.model.configuration import *

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.common.env.artifacts import output_path
from pathlib import Path
from typing import Any
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase
from toffee import CrossDef
from bpuverify.tage.model.constants import TAGE_PAIR_PHASES


def tage_coverage_model():
    return CoverGroupDef(
        "tage_behavior",
        (
            CoverPointDef("lookup", {"miss": Bin.values("miss"), "provider": Bin.values("provider")}),
            CoverPointDef("direction", {"not_taken": Bin.values(0), "taken": Bin.values(1)}),
            CoverPointDef("operation", {
                "cold": Bin.values("cold"),
                "allocate": Bin.values("allocate"),
                "update": Bin.values("update"),
            }),
            CoverPointDef("provider_depth", {
                "none": Bin.values("none"),
                "nonhighest": Bin.values("nonhighest"),
                "highest": Bin.values("highest"),
            }),
        ),
    ).instantiate("kunminghu_v3.tage")


def tage_mixed_writes_coverage_model(mode):
    if mode not in ('update', 'gated'):
        raise ValueError('mixed write coverage mode must be update or gated')
    axis = 'counter' if mode == 'update' else 'reason'
    values = (1, 2) if mode == 'update' else ('saturated', 'mbtb_miss', 'inactive', 'disabled')
    points = (
        CoverPointDef('context', {str(i): Bin.values(i) for i in range(4)}),
        CoverPointDef('way', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef(axis, {str(value): Bin.values(value) for value in values}),
        CoverPointDef('phase', {value: Bin.values(value) for value in ('prepared', 'updated', 'revisited')}),
    )
    return CoverGroupDef('tage_mixed_writes_'+mode, points,
        crosses=(CrossDef('all_dimensions', tuple(point.name for point in points)),)
    ).instantiate('kunminghu_v3.tage.mixed_writes_'+mode)


def write_tage_mixed_writes_coverage(coverage, root, mode):
    if mode not in ('update', 'gated'):
        raise ValueError('mixed write coverage mode must be update or gated')
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root/'results/tage'/f'functional-coverage-mixed-writes-{mode}.json'))


def tage_overlap_coverage_model():
    points = (
        CoverPointDef('context', {str(i): Bin.values(i) for i in range(4)}),
        CoverPointDef('way', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('counter', {str(i): Bin.values(i) for i in (1, 2)}),
        CoverPointDef('mode', {value: Bin.values(value) for value in ('adjacent', 'separated')}),
        CoverPointDef('phase', {value: Bin.values(value) for value in ('prepared', 'updated', 'revisited')}),
    )
    return CoverGroupDef('tage_overlapped_saturation', points,
        crosses=(CrossDef('all_dimensions', tuple(point.name for point in points)),)
    ).instantiate('kunminghu_v3.tage.overlapped_saturation')


def write_tage_overlap_coverage(coverage, root):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root/'results/tage'/'functional-coverage-overlapped-saturation.json'))


def tage_alternate_coverage_model(mode):
    if mode == 'pair':
        points = (
            CoverPointDef('direction', {str(value): Bin.values(value) for value in range(2)}),
            CoverPointDef('slot', {str(value): Bin.values(value) for value in range(4)}),
            CoverPointDef('base_conf', {str(value): Bin.values(value) for value in range(2)}),
            CoverPointDef('phase', {value: Bin.values(value) for value in TAGE_PAIR_PHASES}),
        )
    elif mode == 'mixed':
        points = (
            CoverPointDef('direction', {str(value): Bin.values(value) for value in range(2)}),
            CoverPointDef('slot', {str(value): Bin.values(value) for value in (1, 2, 3)}),
            CoverPointDef('order', {value: Bin.values(value) for value in ('forward', 'reverse')}),
        )
    else:
        raise ValueError('alternate coverage mode must be pair or mixed')
    return CoverGroupDef('tage_alternate_'+mode, points,
        crosses=(CrossDef('all_dimensions', tuple(point.name for point in points)),)
    ).instantiate('kunminghu_v3.tage.alternate_'+mode)


def write_tage_alternate_coverage(coverage, root, mode):
    if mode not in ('pair', 'mixed'):
        raise ValueError('alternate coverage mode must be pair or mixed')
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root/'results/tage'/f'functional-coverage-alternate-{mode}.json'))


def tage_pending_feedback_coverage_model():
    return CoverGroupDef(
        "tage_pending_feedback",
        (
            CoverPointDef("phase", {
                "resident": Bin.values("resident"),
                "saturated_after_burst": Bin.values("saturated_after_burst"),
            }),
        ),
    ).instantiate("kunminghu_v3.tage.pending_feedback")


def write_tage_pending_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / "functional-coverage-pending-feedback.json"))


def tage_interleaved_rows_coverage_model():
    return CoverGroupDef(
        "tage_interleaved_rows",
        (
            CoverPointDef("phase", {
                phase: Bin.values(phase)
                for phase in (
                    "adjacent_resident", "adjacent_saturated", "adjacent_revisit",
                    "serial_resident", "serial_saturated", "serial_revisit",
                )
            }),
            CoverPointDef("context", {f"row_{i}": Bin.values(i) for i in range(4)}),
        ),
        crosses=(CrossDef("phase_by_context", ("phase", "context")),),
    ).instantiate("kunminghu_v3.tage.interleaved_rows")


def write_tage_interleaved_rows_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / "functional-coverage-interleaved-rows.json"))


def tage_dual_rows_coverage_model():
    return CoverGroupDef(
        "tage_dual_rows",
        (
            CoverPointDef("mode", {mode: Bin.values(mode) for mode in ("adjacent", "serial")}),
            CoverPointDef("phase", {
                phase: Bin.values(phase) for phase in ("resident", "saturated", "revisit")
            }),
            CoverPointDef("context", {f"row_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("role", {
                "earlier_not_taken": Bin.values(0), "later_taken": Bin.values(1),
            }),
            CoverPointDef("way", {f"way_{i}": Bin.values(i) for i in range(2)}),
        ),
        crosses=(CrossDef("mode_phase_row_role", ("mode", "phase", "context", "role")),),
    ).instantiate("kunminghu_v3.tage.dual_rows")


def write_tage_dual_rows_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / "functional-coverage-dual-rows.json"))


def write_tage_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / "functional-coverage.json"))


def tage_enable_coverage_model():
    return CoverGroupDef(
        "tage_enable",
        (
            CoverPointDef(
                "phase",
                {
                    "disabled_train_blocked": Bin.values("disabled_train_blocked"),
                    "enabled_train_allocates": Bin.values("enabled_train_allocates"),
                    "disabled_lookup_hidden": Bin.values("disabled_lookup_hidden"),
                    "reenabled_provider_retained": Bin.values("reenabled_provider_retained"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.tage.enable")


def write_tage_enable_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / "functional-coverage-enable.json"))


def tage_training_type_coverage_model():
    return CoverGroupDef(
        "tage_training_type",
        (
            CoverPointDef(
                "phase",
                {
                    "direct_cold_rejected": Bin.values("direct_cold_rejected"),
                    "indirect_cold_rejected": Bin.values("indirect_cold_rejected"),
                    "conditional_allocates": Bin.values("conditional_allocates"),
                    "direct_provider_held": Bin.values("direct_provider_held"),
                    "indirect_provider_held": Bin.values("indirect_provider_held"),
                    "conditional_update_works": Bin.values("conditional_update_works"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.tage.training_type")


def write_tage_training_type_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / "functional-coverage-training-type.json"))


def tage_batch_feedback_coverage_model():
    return CoverGroupDef(
        "tage_batch_feedback",
        (
            CoverPointDef(
                "phase",
                {
                    "two_residents": Bin.values("two_residents"),
                    "both_correct": Bin.values("both_correct"),
                    "independent_counters": Bin.values("independent_counters"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.tage.batch_feedback")


def write_tage_batch_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / "functional-coverage-batch-feedback.json"))


def tage_vector_coverage_model():
    return CoverGroupDef(
        "tage_main_btb_vector",
        (
            CoverPointDef("provider_slot", {
                f"slot{slot}": Bin.values(slot) for slot in range(1, 10)
            }),
            CoverPointDef("association", {
                "serial": Bin.values("serial"),
                "overlap": Bin.values("overlap"),
            }),
        ),
    ).instantiate("kunminghu_v3.tage.main_btb_vector")


def write_tage_vector_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / "functional-coverage-vector.json"))


def tage_mbtb_hit_coverage_model():
    return CoverGroupDef(
        "tage_mbtb_hit",
        (
            CoverPointDef(
                "phase",
                {
                    "cold_miss_rejected": Bin.values("cold_miss_rejected"),
                    "matched_allocates": Bin.values("matched_allocates"),
                    "resident_miss_held": Bin.values("resident_miss_held"),
                    "mixed_vector_hit_only": Bin.values("mixed_vector_hit_only"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.tage.mbtb_hit")


def write_tage_mbtb_hit_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / "functional-coverage-mbtb-hit.json"))


def tage_useful_reset_coverage_model():
    return CoverGroupDef(
        "tage_useful_reset",
        (
            CoverPointDef("allocation", {
                "blocked": Bin.values("blocked"),
                "reopened": Bin.values("reopened"),
            }),
            CoverPointDef("resident_useful", {
                "positive": Bin.values("positive"),
                "cleared": Bin.values("cleared"),
            }),
            CoverPointDef("occupancy", {
                "full": Bin.values(2 * TAGE_TABLES),
                "one_replaced": Bin.values(2 * TAGE_TABLES - 1),
            }),
        ),
    ).instantiate("kunminghu_v3.tage.useful_reset")


def write_tage_useful_reset_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / "functional-coverage-useful-reset.json"))


def tage_base_conf_coverage_model():
    return CoverGroupDef(
        "tage_base_confidence",
        (
            CoverPointDef("base_conf", {
                "low": Bin.values(0),
                "high": Bin.values(1),
            }),
            CoverPointDef("alt_conf", {
                "low": Bin.values(0),
                "high": Bin.values(1),
            }),
        ),
    ).instantiate("kunminghu_v3.tage.base_confidence")


def write_tage_base_conf_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / "functional-coverage-base-conf.json"))


def tage_selector_coverage_model(mode: str):
    """Track asserted selector sharing, batch steps, or provider depths."""

    if mode == "cross_tag":
        points = (
            CoverPointDef("selection", {
                "base_fallback": Bin.values("base_fallback"),
                "provider": Bin.values("provider"),
            }),
            CoverPointDef("probe_counter", {"unchanged_weak": Bin.values(4)}),
        )
    elif mode == "depth":
        points = (
            CoverPointDef("provider_depth", {
                f"table_{depth}": Bin.values(depth) for depth in range(TAGE_TABLES)
            }),
        )
    elif mode == "batch":
        phases = (
            "two_weak_ways", "two_provider_writes", "weak_after_batch",
            "one_decrement", "two_decrements", "third_decrement_selects_provider",
        )
        points = (CoverPointDef("phase", {
            phase: Bin.values(phase) for phase in phases
        }),)
    elif mode == "cancel":
        phases = (
            "two_weak_ways", "opposite_provider_writes",
            "net_zero_fallback", "one_decrement_selects_provider",
        )
        points = (CoverPointDef("phase", {
            phase: Bin.values(phase) for phase in phases
        }),)
    else:
        raise ValueError(f"unsupported TAGE selector coverage mode: {mode}")
    return CoverGroupDef(f"tage_selector_{mode}", points).instantiate(
        f"kunminghu_v3.tage.selector.{mode}"
    )


def write_tage_selector_coverage(coverage: Any, root: Path, name: str) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / f"functional-coverage-selector-{name}.json"))


def tage_resolve_slot_coverage_model(mode):
    if mode == 'provider':
        points = (
            CoverPointDef('slot', {f'slot_{i}': Bin.values(i) for i in range(8)}),
            CoverPointDef('direction', {f'direction_{i}': Bin.values(i) for i in range(2)}),
            CoverPointDef('depth', {f'table_{i}': Bin.values(i) for i in range(TAGE_TABLES)}),
            CoverPointDef('phase', {name: Bin.values(name) for name in (
                'allocated', 'strengthened', 'near_saturated', 'saturated', 'held',
            )}),
        )
    elif mode == 'qualification':
        points = (
            CoverPointDef('slot', {f'slot_{i}': Bin.values(i) for i in range(8)}),
            CoverPointDef('reason', {name: Bin.values(name) for name in (
                'mbtb_miss', 'direct', 'indirect', 'inactive', 'disabled',
                'qualified_missed_neighbor', 'qualified_nonconditional_neighbor',
            )}),
        )
    else:
        raise ValueError('TAGE resolve mode must be provider or qualification')
    dimensions = tuple(point.name for point in points)
    return CoverGroupDef(f'tage_resolve_{mode}', points,
                         crosses=(CrossDef('_'.join(dimensions), dimensions),)).instantiate(
        f'kunminghu_v3.tage.resolve_{mode}'
    )


def write_tage_resolve_slot_coverage(coverage, root, mode):
    if mode not in ('provider', 'qualification'):
        raise ValueError('TAGE resolve mode must be provider or qualification')
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / 'results' / 'tage' / f'functional-coverage-resolve-{mode}.json'))


def tage_way_migration_coverage_model(mode: str):
    if mode not in ("current", "captured"):
        raise ValueError(f"unsupported TAGE way migration mode: {mode}")
    return CoverGroupDef(
        "tage_way_migration",
        (
            CoverPointDef("context", {f"row_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("origin_way", {f"way_{i}": Bin.values(i) for i in range(2)}),
            CoverPointDef("phase", {name: Bin.values(name) for name in
                ("migrated", "feedback", "mixed_pipeline")}),
            CoverPointDef("check", {name: Bin.values(name) for name in
                ("target_counter", "target_useful", "neighbor_counter", "neighbor_useful", "other_neighbors")}),
        ),
        crosses=(CrossDef("context_direction_phase_check", ("context", "origin_way", "phase", "check")),),
    ).instantiate(f"kunminghu_v3.tage.way_migration_{mode}")


def write_tage_way_migration_coverage(coverage: Any, root: Path, mode: str) -> None:
    if mode not in ("current", "captured"):
        raise ValueError(f"unsupported TAGE way migration mode: {mode}")
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "tage" / f"functional-coverage-way-migration-{mode}.json"))
