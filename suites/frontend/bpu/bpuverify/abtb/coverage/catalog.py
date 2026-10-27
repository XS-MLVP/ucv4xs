"""bpuverify.abtb.coverage.catalog components."""

from __future__ import annotations

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.common.env.artifacts import output_path
from pathlib import Path
from typing import Any
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase


def abtb_coverage_model():
    return CoverGroupDef(
        "abtb_prediction",
        (
            CoverPointDef(
                "phase", {"cold": Bin.values("cold"), "trained": Bin.values("trained")}
            ),
            CoverPointDef(
                "result", {"miss": Bin.values("miss"), "hit": Bin.values("hit")}
            ),
            CoverPointDef(
                "branch_type",
                {
                    "conditional": Bin.values(1),
                    "direct": Bin.values(2),
                    "indirect": Bin.values(3),
                },
            ),
            CoverPointDef(
                "bank_mask",
                {
                    "bank_0": Bin.values(1),
                    "bank_1": Bin.values(2),
                    "bank_2": Bin.values(4),
                    "bank_3": Bin.values(8),
                },
            ),
            CoverPointDef(
                "history_class",
                {
                    "zero": Bin.values("zero"),
                    "nonzero": Bin.values("nonzero"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb")


def abtb_enable_coverage_model():
    """Assertion-backed global enable phases, independent of RTL line counts."""

    return CoverGroupDef(
        "abtb_enable",
        (
            CoverPointDef(
                "phase",
                {
                    name: Bin.values(name)
                    for name in (
                        "disabled_allocate_blocked",
                        "enabled_allocate",
                        "disabled_lookup_hidden",
                        "reenabled_hit_retained",
                        "disabled_update_blocked",
                        "enabled_update",
                    )
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.enable")


def write_abtb_enable_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-enable.json"))


def abtb_position_order_coverage_model():
    return CoverGroupDef(
        "abtb_position_order",
        (
            CoverPointDef(
                "transition",
                {
                    "later_taken_suppresses_earlier": Bin.values("suppress"),
                    "earlier_taken_restores_earlier": Bin.values("restore"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.position_order")


def abtb_position_replacement_coverage_model():
    return CoverGroupDef(
        "abtb_position_replacement",
        (
            CoverPointDef(
                "phase",
                {
                    "full_set": Bin.values("full_set"),
                    "later_taken_suppresses_survivors": Bin.values(
                        "later_taken_suppresses_survivors"
                    ),
                    "victim_replaced": Bin.values("victim_replaced"),
                    "earlier_taken_restores_only_self": Bin.values(
                        "earlier_taken_restores_only_self"
                    ),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.position_replacement")


def abtb_position_victim_matrix_coverage_model():
    return CoverGroupDef(
        "abtb_position_victim_matrix",
        (
            CoverPointDef(
                "victim_way",
                {f"way_{way}": Bin.values(way) for way in range(4)},
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.position_victim_matrix")


def abtb_multi_position_direction_coverage_model():
    return CoverGroupDef(
        "abtb_multi_position_direction",
        (
            CoverPointDef(
                "phase",
                {
                    "not_taken_decreases_all": Bin.values("not_taken_decreases_all"),
                    "taken_restores_only_equal": Bin.values("taken_restores_only_equal"),
                    "earlier_decrease_proven": Bin.values("earlier_decrease_proven"),
                    "later_unchanged_proven": Bin.values("later_unchanged_proven"),
                    "remaining_position_recovers": Bin.values(
                        "remaining_position_recovers"
                    ),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.multi_position_direction")


def abtb_hash_position_direction_coverage_model():
    return CoverGroupDef(
        "abtb_hash_position_direction",
        (
            CoverPointDef(
                "scenario",
                {
                    "two_distinct_profiles": Bin.values("two_distinct_profiles"),
                    "negative_set_isolated": Bin.values("negative_set_isolated"),
                    **{f"recovered_way_{way}": Bin.values(f"recovered_way_{way}") for way in range(4)},
                    "mixed_set_preserved": Bin.values("mixed_set_preserved"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.hash_position_direction")


def abtb_cross_bank_direction_coverage_model():
    return CoverGroupDef(
        "abtb_cross_bank_direction",
        (
            CoverPointDef("transition", {
                **{
                    f"bank_{bank}_aged": Bin.values(f"bank_{bank}_aged")
                    for bank in range(4)
                },
                **{
                    f"bank_{bank}_way_{way}_recovered": Bin.values(
                        f"bank_{bank}_way_{way}_recovered"
                    )
                    for bank in range(4) for way in range(4)
                },
            }),
        ),
    ).instantiate("kunminghu_v3.abtb.cross_bank_direction")


def abtb_cross_bank_replacement_coverage_model():
    return CoverGroupDef(
        "abtb_cross_bank_replacement",
        (
            CoverPointDef("transition", {
                **{
                    f"bank_{bank}_replacement": Bin.values(f"bank_{bank}_replacement")
                    for bank in range(4)
                },
                **{
                    f"bank_{bank}_aged": Bin.values(f"bank_{bank}_aged")
                    for bank in range(4)
                },
                **{
                    f"bank_{bank}_way_{way}_recovered": Bin.values(
                        f"bank_{bank}_way_{way}_recovered"
                    )
                    for bank in range(4) for way in range(4)
                },
            }),
        ),
    ).instantiate("kunminghu_v3.abtb.cross_bank_replacement")


def abtb_microtage_vector_coverage_model():
    return CoverGroupDef(
        "abtb_microtage_vector",
        (
            CoverPointDef("profile", {
                "mixed_weak": Bin.values("mixed_weak"),
                "conditional_strong_negative": Bin.values("conditional_strong_negative"),
            }),
            CoverPointDef("transition", {
                "start": Bin.values("start"),
                "weak_to_strong": Bin.values("weak_to_strong"),
                "strong_to_weak": Bin.values("strong_to_weak"),
            }),
        ),
    ).instantiate("kunminghu_v3.abtb.microtage_vector")


def abtb_mixed_position_type_coverage_model():
    return CoverGroupDef(
        "abtb_mixed_position_type",
        (
            CoverPointDef(
                "phase",
                {
                    "mixed_type_fill": Bin.values("mixed_type_fill"),
                    "conditional_only_decrease": Bin.values(
                        "conditional_only_decrease"
                    ),
                    "negative_saturation_proven": Bin.values(
                        "negative_saturation_proven"
                    ),
                    "conditional_recovery": Bin.values("conditional_recovery"),
                    "indirect_target_correction": Bin.values(
                        "indirect_target_correction"
                    ),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.mixed_position_type")


def abtb_mixed_type_replacement_coverage_model():
    return CoverGroupDef(
        "abtb_mixed_type_replacement",
        (
            CoverPointDef(
                "scenario",
                {
                    **{f"way_{way}": Bin.values(f"way_{way}") for way in range(4)},
                    "victim_conditional": Bin.values("victim_conditional"),
                    "victim_direct": Bin.values("victim_direct"),
                    "victim_indirect": Bin.values("victim_indirect"),
                    "weak_positive": Bin.values("weak_positive"),
                    "not_taken": Bin.values("not_taken"),
                    "recovered": Bin.values("recovered"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.mixed_type_replacement")


def abtb_replacement_coverage_model():
    return CoverGroupDef(
        "abtb_replacement",
        (
            CoverPointDef(
                "victim_way",
                {f"way_{way}": Bin.values(way) for way in range(4)},
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.replacement")


def abtb_recovery_coverage_model():
    return CoverGroupDef(
        "abtb_recovery",
        (
            CoverPointDef(
                "stage_result",
                {
                    f"{stage}_{result}": Bin.values(f"{stage}_{result}")
                    for stage in ("s2", "s3")
                    for result in ("hit", "miss")
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.recovery")


def abtb_max_set_coverage_model():
    return CoverGroupDef(
        "abtb_max_set",
        (
            CoverPointDef(
                "bank_mask",
                {f"bank_{bank}": Bin.values(1 << bank) for bank in range(4)},
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.max_set")


def abtb_boundary_replacement_coverage_model():
    return CoverGroupDef(
        "abtb_boundary_replacement",
        (
            CoverPointDef(
                "bank_mask",
                {f"bank_{bank}": Bin.values(1 << bank) for bank in range(4)},
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.boundary_replacement")


def abtb_boundary_direction_coverage_model():
    return CoverGroupDef(
        "abtb_boundary_direction",
        (
            CoverPointDef(
                "bank_way_transition",
                {
                    f"bank_{bank}_way_{way}_{transition}": Bin.values(
                        f"bank_{bank}_way_{way}_{transition}"
                    )
                    for bank in range(4)
                    for way in range(4)
                    for transition in ("negative_saturated", "positive_saturated")
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.boundary_direction")


def abtb_boundary_counter_reset_coverage_model():
    return CoverGroupDef(
        "abtb_boundary_counter_reset",
        (
            CoverPointDef(
                "bank_way_reset",
                {
                    f"bank_{bank}_way_{way}": Bin.values(f"bank_{bank}_way_{way}")
                    for bank in range(4)
                    for way in range(4)
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.boundary_counter_reset")


def abtb_interior_direction_coverage_model():
    return CoverGroupDef(
        "abtb_interior_direction",
        (
            CoverPointDef(
                "cell_transition",
                {
                    f"bank_{bank}_set_{set_index}_way_{way}_{transition}":
                    Bin.values(f"bank_{bank}_set_{set_index}_way_{way}_{transition}")
                    for bank, set_index in ((3, 16), (1, 34))
                    for way in range(4)
                    for transition in ("negative_saturated", "positive_saturated")
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.interior_direction")


def abtb_adjacent_set_direction_coverage_model():
    return CoverGroupDef(
        "abtb_adjacent_set_direction",
        (
            CoverPointDef(
                "set_35_transition",
                {
                    f"way_{way}_{direction}": Bin.values(
                        f"way_{way}_{direction}"
                    )
                    for way in range(4)
                    for direction in ("negative", "positive")
                },
            ),
            CoverPointDef(
                "neighbor_state",
                {"set_34_preserved": Bin.values("set_34_preserved")},
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.adjacent_set_direction")


def abtb_wrap_set_direction_coverage_model():
    return CoverGroupDef(
        "abtb_wrap_set_direction",
        (
            CoverPointDef(
                "set_0_transition",
                {
                    f"bank_{bank}_way_{way}_{direction}": Bin.values(
                        f"bank_{bank}_way_{way}_{direction}"
                    )
                    for bank in (1, 2)
                    for way in range(4)
                    for direction in ("negative", "positive")
                },
            ),
            CoverPointDef(
                "edge_neighbor",
                {"set_63_preserved": Bin.values("set_63_preserved")},
            ),
            CoverPointDef(
                "other_bank",
                {
                    f"bank_{bank}_with_neighbor_stable": Bin.values(
                        f"bank_{bank}_with_neighbor_stable"
                    )
                    for bank in (1, 2)
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.wrap_set_direction")


def abtb_target_region_coverage_model():
    return CoverGroupDef(
        "abtb_target_region",
        (
            CoverPointDef(
                "target_region",
                {
                    name: Bin.values(name)
                    for name in ("fit", "overflow_wrap", "underflow_wrap")
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.target_region")


def abtb_hash_set_coverage_model():
    return CoverGroupDef(
        "abtb_hash_set",
        (
            CoverPointDef(
                "set_index",
                {f"set_{index}": Bin.values(index) for index in range(4)},
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.hash_set")


def abtb_high_hash_grid_coverage_model():
    sets = range(48, 52)
    banks = range(4)
    return CoverGroupDef(
        "abtb_high_hash_grid",
        (
            CoverPointDef(
                "route",
                {
                    f"set_{set_index}_bank_{bank}": Bin.values(
                        f"set_{set_index}_bank_{bank}"
                    )
                    for set_index in sets
                    for bank in banks
                },
            ),
            CoverPointDef(
                "direction",
                {
                    f"set_{set_index}_bank_{bank}_{transition}": Bin.values(
                        f"set_{set_index}_bank_{bank}_{transition}"
                    )
                    for set_index in sets
                    for bank in banks
                    for transition in ("negative", "positive")
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.high_hash_grid")


def write_abtb_high_hash_grid_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-high-hash-grid.json"))


def abtb_high_hash_full_way_coverage_model():
    return CoverGroupDef(
        "abtb_high_hash_full_way",
        (
            CoverPointDef(
                "route_way",
                {
                    f"set_{set_index}_bank_{bank}_way_{way}": Bin.values(
                        f"set_{set_index}_bank_{bank}_way_{way}"
                    )
                    for set_index in range(48, 52)
                    for bank in range(4)
                    for way in range(4)
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.high_hash_full_way")


def write_abtb_high_hash_full_way_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-high-hash-full-way.json"))


def abtb_high_hash_replacement_coverage_model():
    return CoverGroupDef(
        "abtb_high_hash_replacement",
        (
            CoverPointDef(
                "route",
                {
                    f"set_{set_index}_bank_{bank}": Bin.values(
                        f"set_{set_index}_bank_{bank}"
                    )
                    for set_index in range(48, 52)
                    for bank in range(4)
                },
            ),
            CoverPointDef(
                "isolation",
                {"peers_preserved": Bin.values("peers_preserved")},
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.high_hash_replacement")


def write_abtb_high_hash_replacement_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-high-hash-replacement.json"))


def abtb_hash_replacement_coverage_model():
    return CoverGroupDef(
        "abtb_hash_replacement",
        (
            CoverPointDef(
                "victim_way",
                {f"way_{way}": Bin.values(way) for way in range(4)},
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.hash_replacement")


def abtb_middle_boundary_coverage_model():
    return CoverGroupDef(
        "abtb_middle_boundary",
        (
            CoverPointDef(
                "cell_transition",
                {
                    f"set_{set_index}_bank_{bank}_way_{way}_{direction}":
                    Bin.values(f"set_{set_index}_bank_{bank}_way_{way}_{direction}")
                    for set_index in (31, 32)
                    for bank in range(4)
                    for way in range(4)
                    for direction in ("negative", "positive")
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.middle_boundary")


def abtb_three_set_neighborhood_coverage_model():
    return CoverGroupDef(
        "abtb_three_set_neighborhood",
        (
            CoverPointDef(
                "cell_transition",
                {
                    f"bank_{bank}_way_{way}_{direction}": Bin.values(
                        f"bank_{bank}_way_{way}_{direction}"
                    )
                    for bank in range(4)
                    for way in range(4)
                    for direction in ("negative", "positive")
                },
            ),
            CoverPointDef("flanks", {"both_preserved": Bin.values("both_preserved")}),
            CoverPointDef(
                "active_bank",
                {f"bank_{bank}": Bin.values(bank) for bank in range(4)},
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.three_set_neighborhood")


def write_abtb_three_set_neighborhood_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-three-set-neighborhood.json"))


def abtb_flanked_replacement_coverage_model():
    return CoverGroupDef(
        "abtb_flanked_replacement",
        (
            CoverPointDef(
                "replaced_bank",
                {f"bank_{bank}": Bin.values(bank) for bank in range(4)},
            ),
            CoverPointDef(
                "isolation",
                {"both_flanks_and_peers": Bin.values("both_flanks_and_peers")},
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.flanked_replacement")


def write_abtb_flanked_replacement_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-flanked-replacement.json"))


def abtb_flanked_recovery_coverage_model():
    return CoverGroupDef(
        "abtb_flanked_recovery",
        (
            CoverPointDef(
                "recovered_cell",
                {
                    f"bank_{bank}_way_{way}": Bin.values(
                        f"bank_{bank}_way_{way}"
                    )
                    for bank in range(4)
                    for way in range(4)
                },
            ),
            CoverPointDef("entry_origin", {
                "survivor": Bin.values("survivor"),
                "replacement": Bin.values("replacement"),
            }),
            CoverPointDef("isolation", {
                "both_flanks_and_peers": Bin.values("both_flanks_and_peers")
            }),
        ),
    ).instantiate("kunminghu_v3.abtb.flanked_recovery")


def write_abtb_flanked_recovery_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-flanked-recovery.json"))


def abtb_interior_replacement_coverage_model():
    return CoverGroupDef(
        "abtb_interior_replacement",
        (
            CoverPointDef(
                "victim_way",
                {f"way_{way}": Bin.values(way) for way in range(4)},
            ),
            CoverPointDef(
                "sentinel",
                {"preserved": Bin.values("preserved")},
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.interior_replacement")


def abtb_multi_hit_coverage_model():
    return CoverGroupDef(
        "abtb_multi_hit_cleanup",
        (
            CoverPointDef(
                "bank_phase",
                {
                    f"bank_{bank}_{phase}": Bin.values(f"bank_{bank}_{phase}")
                    for bank in (0, 2)
                    for phase in ("duplicate", "cleaned")
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.multi_hit")


def abtb_buffered_training_coverage_model():
    return CoverGroupDef(
        "abtb_buffered_training",
        (
            CoverPointDef(
                "set_phase",
                {
                    f"set_{set_index}_{phase}": Bin.values(
                        f"set_{set_index}_{phase}"
                    )
                    for set_index in (0, 1)
                    for phase in ("pending", "committed")
                },
            ),
        ),
    ).instantiate("kunminghu_v3.abtb.buffered_training")


def write_abtb_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage.json"))


def write_abtb_position_order_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-position-order.json"))


def write_abtb_position_replacement_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-position-replacement.json"))


def write_abtb_position_victim_matrix_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-position-victim-matrix.json"))


def write_abtb_multi_position_direction_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-multi-position-direction.json"))


def write_abtb_hash_position_direction_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-hash-position-direction.json"))


def write_abtb_cross_bank_direction_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-cross-bank-direction.json"))


def write_abtb_cross_bank_replacement_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-cross-bank-replacement.json"))


def write_abtb_microtage_vector_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-microtage-vector.json"))


def write_abtb_mixed_position_type_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-mixed-position-type.json"))


def write_abtb_mixed_type_replacement_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-mixed-type-replacement.json"))


def write_abtb_replacement_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-replacement.json"))


def write_abtb_recovery_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-recovery.json"))


def write_abtb_max_set_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-max-set.json"))


def write_abtb_boundary_replacement_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-boundary-replacement.json"))


def write_abtb_boundary_direction_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-boundary-direction.json"))


def write_abtb_boundary_counter_reset_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-boundary-counter-reset.json"))


def write_abtb_interior_direction_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-interior-direction.json"))


def write_abtb_adjacent_set_direction_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-adjacent-set-direction.json"))


def write_abtb_wrap_set_direction_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-wrap-set-direction.json"))


def write_abtb_target_region_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-target-region.json"))


def write_abtb_hash_set_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-hash-set.json"))


def write_abtb_hash_replacement_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-hash-replacement.json"))


def write_abtb_middle_boundary_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-middle-boundary.json"))


def write_abtb_interior_replacement_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-interior-replacement.json"))


def write_abtb_multi_hit_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-multi-hit.json"))


def write_abtb_buffered_training_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "abtb" / "functional-coverage-buffered-training.json"))
