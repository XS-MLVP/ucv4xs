"""suites.frontend.bpu.bpu.coverage.catalog components."""

from __future__ import annotations

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.runtime.artifacts import output_path
from pathlib import Path
from typing import Any
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CoverageDatabase


def bpu_coverage_model():
    return CoverGroupDef(
        "bpu_integration",
        (
            CoverPointDef(
                "phase",
                {
                    "cold": Bin.values("cold"),
                    "trained": Bin.values("trained"),
                    "disabled": Bin.values("disabled"),
                },
            ),
            CoverPointDef(
                "taken", {"no": Bin.values(0), "yes": Bin.values(1)}
            ),
            CoverPointDef(
                "control",
                {
                    "redirect": Bin.values("redirect"),
                    "redirect_stalled": Bin.values("redirect_stalled"),
                    "stream": Bin.values("stream"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.bpu")


def write_bpu_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage.json"))


def bpu_s2_repair_coverage_model():
    return CoverGroupDef(
        "bpu_s2_repair",
        (
            CoverPointDef("stage", {
                "s1_miss": Bin.values("s1_miss"),
                "s2_repair": Bin.values("s2_repair"),
            }),
            CoverPointDef("taken", {
                "not_taken": Bin.values(0),
                "taken": Bin.values(1),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.s2_repair")


def write_bpu_s2_repair_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-s2-repair.json"))


def bpu_target_boundary_coverage_model():
    return CoverGroupDef(
        "bpu_target_boundary",
        (
            CoverPointDef(
                "direction",
                {
                    "overflow": Bin.values("overflow"),
                    "underflow": Bin.values("underflow"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.bpu.target_boundary")


def write_bpu_target_boundary_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-target-boundary.json"))


def bpu_s3_target_coverage_model():
    return CoverGroupDef(
        "bpu_s3_target_correction",
        (
            CoverPointDef(
                "stage_target",
                {
                    "s1_old": Bin.values("s1_old"),
                    "s3_new": Bin.values("s3_new"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.bpu.s3_target")


def write_bpu_s3_target_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-s3-target.json"))


def bpu_ittage_selection_coverage_model():
    return CoverGroupDef(
        "bpu_ittage_selection",
        (
            CoverPointDef(
                "phase",
                {
                    phase: Bin.values(phase)
                    for phase in (
                        "provider_resident", "mbtb_only_target",
                        "s2_mbtb_target", "s3_ittage_target",
                    )
                },
            ),
        ),
    ).instantiate("kunminghu_v3.bpu.ittage_selection")


def write_bpu_ittage_selection_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-ittage-selection.json"))


def bpu_nested_ras_coverage_model():
    return CoverGroupDef(
        "bpu_nested_ras",
        (
            CoverPointDef(
                "phase",
                {
                    phase: Bin.values(phase)
                    for phase in (
                        "outer_call", "inner_call", "inner_return_mbtb",
                        "inner_return_ras", "outer_return_mbtb",
                        "outer_return_ras",
                    )
                },
            ),
        ),
    ).instantiate("kunminghu_v3.bpu.nested_ras")


def write_bpu_nested_ras_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-nested-ras.json"))


def bpu_abtb_s3_correction_coverage_model():
    return CoverGroupDef(
        "bpu_abtb_s3_correction",
        (
            CoverPointDef(
                "phase",
                {
                    "ahead_s1_old": Bin.values("ahead_s1_old"),
                    "main_s3_cross_region": Bin.values("main_s3_cross_region"),
                    "same_cycle_source_echo": Bin.values("same_cycle_source_echo"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.bpu.abtb_s3_correction")


def write_bpu_abtb_s3_correction_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-abtb-s3-correction.json"))


def bpu_abtb_wrap_coverage_model():
    return CoverGroupDef(
        "bpu_abtb_wrap",
        (
            CoverPointDef(
                "phase",
                {
                    "main_forward_full": Bin.values("main_forward_full"),
                    "main_return_full": Bin.values("main_return_full"),
                    "ahead_return_wrapped": Bin.values("ahead_return_wrapped"),
                    "ahead_source_echo": Bin.values("ahead_source_echo"),
                    "later_full_target": Bin.values("later_full_target"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.bpu.abtb_wrap")


def write_bpu_abtb_wrap_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-abtb-wrap.json"))


def bpu_abtb_fasttrain_coverage_model():
    return CoverGroupDef(
        "bpu_abtb_fasttrain",
        (
            CoverPointDef(
                "source_phase",
                {
                    "main_btb_s2": Bin.values("main_btb_s2"),
                    "ahead_btb_s1": Bin.values("ahead_btb_s1"),
                    "main_btb_fallback": Bin.values("main_btb_fallback"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.bpu.abtb_fasttrain")


def write_bpu_abtb_fasttrain_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-abtb-fasttrain.json"))


def bpu_early_source_isolation_coverage_model():
    return CoverGroupDef(
        "bpu_early_source_isolation",
        (
            CoverPointDef(
                "configuration",
                {
                    "micro_initial": Bin.values("micro_initial"),
                    "ahead_only": Bin.values("ahead_only"),
                    "micro_retained": Bin.values("micro_retained"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.bpu.early_source_isolation")


def write_bpu_early_source_isolation_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-early-source-isolation.json"))


def bpu_early_source_arbitration_coverage_model():
    return CoverGroupDef(
        "bpu_early_source_arbitration",
        (
            CoverPointDef(
                "observation",
                {
                    "ahead_entry_valid": Bin.values("ahead_entry_valid"),
                    "dual_enabled_ahead_selected": Bin.values("dual_enabled_ahead_selected"),
                    "same_s1_micro_revealed": Bin.values("same_s1_micro_revealed"),
                    "resumed_pipeline_ahead_selected": Bin.values("resumed_pipeline_ahead_selected"),
                    "resumed_pipeline_micro_adapts": Bin.values("resumed_pipeline_micro_adapts"),
                    "adjacent_resolve_retargets_micro": Bin.values("adjacent_resolve_retargets_micro"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.bpu.early_source_arbitration")


def write_bpu_early_source_arbitration_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-early-source-arbitration.json"))


def bpu_batch_feedback_coverage_model():
    return CoverGroupDef(
        "bpu_batch_feedback",
        (
            CoverPointDef("phase", {
                "first_resident": Bin.values("first_resident"),
                "late_allocation_and_early_decrement": Bin.values(
                    "late_allocation_and_early_decrement"
                ),
                "both_correct_updates": Bin.values("both_correct_updates"),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.batch_feedback")


def write_bpu_batch_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-batch-feedback.json"))


def bpu_tage_batch_feedback_coverage_model():
    return CoverGroupDef(
        "bpu_tage_batch_feedback",
        (
            CoverPointDef("phase", {
                "two_mbtb_residents": Bin.values("two_mbtb_residents"),
                "single_provider_control": Bin.values("single_provider_control"),
                "two_distinct_providers": Bin.values("two_distinct_providers"),
                "both_provider_counters_updated": Bin.values(
                    "both_provider_counters_updated"
                ),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.tage_batch_feedback")


def write_bpu_tage_batch_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-tage-batch-feedback.json"))


def bpu_sc_batch_feedback_coverage_model():
    return CoverGroupDef(
        "bpu_sc_batch_feedback",
        (
            CoverPointDef("phase", {
                "two_providers_qualified": Bin.values("two_providers_qualified"),
                "single_branch_control": Bin.values("single_branch_control"),
                "same_beat_dual_feedback": Bin.values("same_beat_dual_feedback"),
                "provider_state_held": Bin.values("provider_state_held"),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.sc_batch_feedback")


def write_bpu_sc_batch_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-sc-batch-feedback.json"))


def bpu_sc_same_way_feedback_coverage_model():
    return CoverGroupDef(
        "bpu_sc_same_way_feedback",
        (
            CoverPointDef("phase", {
                "qualified_pair": Bin.values("qualified_pair"),
                "single_four_pending": Bin.values("single_four_pending"),
                "single_eight_learned": Bin.values("single_eight_learned"),
                "dual_four_learned": Bin.values("dual_four_learned"),
                "provider_state_held": Bin.values("provider_state_held"),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.sc_same_way_feedback")


def write_bpu_sc_same_way_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-sc-same-way-feedback.json"))


def bpu_sc_same_way_cancel_coverage_model():
    return CoverGroupDef(
        "bpu_sc_same_way_cancel",
        (
            CoverPointDef("phase", {
                "qualified_pair": Bin.values("qualified_pair"),
                "opposite_feedback_cancelled": Bin.values(
                    "opposite_feedback_cancelled"
                ),
                "single_branch_control": Bin.values("single_branch_control"),
                "reset_reproducible": Bin.values("reset_reproducible"),
                "dual_vector_after_cancel": Bin.values("dual_vector_after_cancel"),
                "provider_state_held": Bin.values("provider_state_held"),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.sc_same_way_cancel")


def write_bpu_sc_same_way_cancel_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-sc-same-way-cancel.json"))


def bpu_fresh_feedback_coverage_model():
    return CoverGroupDef(
        "bpu_fresh_feedback",
        (
            CoverPointDef("phase", {
                "qualified_pair": Bin.values("qualified_pair"),
                "paired_metadata_advanced": Bin.values("paired_metadata_advanced"),
                "both_tage_counters_saturated": Bin.values(
                    "both_tage_counters_saturated"
                ),
                "sc_threshold_crossed": Bin.values("sc_threshold_crossed"),
                "learned_state_persists": Bin.values("learned_state_persists"),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.fresh_feedback")


def write_bpu_fresh_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-fresh-feedback.json"))


def bpu_adjacent_feedback_coverage_model():
    return CoverGroupDef(
        "bpu_adjacent_feedback",
        (
            CoverPointDef("phase", {
                "distinct_paired_metadata": Bin.values("distinct_paired_metadata"),
                "adjacent_acceptance": Bin.values("adjacent_acceptance"),
                "both_provider_cells_updated": Bin.values("both_provider_cells_updated"),
                "both_mbtb_slots_updated": Bin.values("both_mbtb_slots_updated"),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.adjacent_feedback")


def write_bpu_adjacent_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-adjacent-feedback.json"))


def bpu_cross_pc_feedback_coverage_model():
    return CoverGroupDef(
        "bpu_cross_pc_feedback",
        (
            CoverPointDef("phase", {
                "two_pc_entries": Bin.values("two_pc_entries"),
                "distinct_paired_metadata": Bin.values("distinct_paired_metadata"),
                "adjacent_acceptance": Bin.values("adjacent_acceptance"),
                "prediction_overlap": Bin.values("prediction_overlap"),
                "opposite_counter_updates": Bin.values("opposite_counter_updates"),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.cross_pc_feedback")


def write_bpu_cross_pc_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-cross-pc-feedback.json"))


def bpu_history_feedback_coverage_model():
    return CoverGroupDef(
        "bpu_history_feedback",
        (
            CoverPointDef("phase", {
                "reference_provider": Bin.values("reference_provider"),
                "alternate_history_miss": Bin.values("alternate_history_miss"),
                "separate_provider_cells": Bin.values("separate_provider_cells"),
                "adjacent_acceptance": Bin.values("adjacent_acceptance"),
                "both_contexts_updated": Bin.values("both_contexts_updated"),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.history_feedback")


def write_bpu_history_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-history-feedback.json"))


def bpu_history_stream_overlap_coverage_model():
    return CoverGroupDef(
        "bpu_history_stream_overlap",
        (
            CoverPointDef("phase", {
                "two_history_cells_prepared": Bin.values(
                    "two_history_cells_prepared"
                ),
                "bank_disjoint_stream": Bin.values("bank_disjoint_stream"),
                "adjacent_feedback": Bin.values("adjacent_feedback"),
                "prediction_overlap": Bin.values("prediction_overlap"),
                "both_cells_updated": Bin.values("both_cells_updated"),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.history_stream_overlap")


def write_bpu_history_stream_overlap_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-history-stream-overlap.json"))


def bpu_same_bank_training_coverage_model():
    return CoverGroupDef(
        "bpu_same_bank_training",
        (
            CoverPointDef("phase", {
                "provider_and_stream_prepared": Bin.values("provider_and_stream_prepared"),
                "prediction_reads_active": Bin.values("prediction_reads_active"),
                "feedback_held": Bin.values("feedback_held"),
                "accepted_after_release": Bin.values("accepted_after_release"),
                "training_effect_readback": Bin.values("training_effect_readback"),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.same_bank_training")


def write_bpu_same_bank_training_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-same-bank-training.json"))


def bpu_same_bank_burst_coverage_model():
    return CoverGroupDef(
        "bpu_same_bank_burst",
        (
            CoverPointDef("phase", {
                "two_history_cells": Bin.values("two_history_cells"),
                "same_bank_stream": Bin.values("same_bank_stream"),
                "both_beats_held": Bin.values("both_beats_held"),
                "adjacent_release": Bin.values("adjacent_release"),
                "first_history_updated": Bin.values("first_history_updated"),
                "second_history_updated": Bin.values("second_history_updated"),
            }),
        ),
    ).instantiate("kunminghu_v3.bpu.same_bank_burst")


def write_bpu_same_bank_burst_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "bpu" / "functional-coverage-same-bank-burst.json"))
