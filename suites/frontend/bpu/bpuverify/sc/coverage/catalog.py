"""bpuverify.sc.coverage.catalog components."""

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


def sc_coverage_model():
    return CoverGroupDef(
        "sc_behavior",
        (
            CoverPointDef("decision", {"not_used": Bin.values("not_used"), "used": Bin.values("used")}),
            CoverPointDef("sc_direction", {"not_taken": Bin.values(0), "taken": Bin.values(1)}),
            CoverPointDef(
                "training",
                {
                    "toward_nt": Bin.values(0),
                    "toward_t": Bin.values(1),
                    "not_applicable": Bin.values("none"),
                },
            ),
            CoverPointDef(
                "qualification",
                {
                    "valid_conditional": Bin.values("valid_conditional"),
                    "provider_invalid": Bin.values("provider_invalid"),
                    "mbtb_miss": Bin.values("mbtb_miss"),
                    "nonconditional": Bin.values("nonconditional"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.sc")


def write_sc_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage.json"))


def sc_pipeline_coverage_model():
    return CoverGroupDef(
        "sc_pipeline",
        (
            CoverPointDef(
                "qualification_transition",
                {
                    "valid_to_miss": Bin.values("valid_conditional->mbtb_miss"),
                    "miss_to_provider_invalid": Bin.values("mbtb_miss->provider_invalid"),
                    "provider_invalid_to_nonconditional": Bin.values(
                        "provider_invalid->nonconditional"
                    ),
                    "nonconditional_to_valid": Bin.values(
                        "nonconditional->valid_conditional"
                    ),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.sc.pipeline")


def write_sc_pipeline_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-pipeline.json"))


def sc_vector_coverage_model():
    return CoverGroupDef(
        "sc_main_btb_vector",
        (
            CoverPointDef("used_slot", {
                f"slot{i}": Bin.values(i) for i in range(1, RESULT_SLOTS)
            }),
            CoverPointDef("association", {
                "serial": Bin.values("serial"),
                "overlap": Bin.values("overlap"),
            }),
        ),
    ).instantiate("kunminghu_v3.sc.main_btb_vector")


def write_sc_vector_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-vector.json"))


def sc_batch_feedback_coverage_model():
    return CoverGroupDef(
        "sc_batch_feedback",
        (
            CoverPointDef("resolved_slot", {
                "first": Bin.values(0),
                "after_gap": Bin.values(2),
            }),
            CoverPointDef("predicted_slot", {
                "slot1": Bin.values(1),
                "slot3": Bin.values(3),
            }),
            CoverPointDef("direction", {
                "not_taken": Bin.values(0),
                "taken": Bin.values(1),
            }),
        ),
    ).instantiate("kunminghu_v3.sc.batch_feedback")


def write_sc_batch_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-batch-feedback.json"))


def sc_adjacent_feedback_coverage_model():
    return CoverGroupDef(
        "sc_adjacent_feedback",
        (
            CoverPointDef("phase", {
                "cold": Bin.values("cold"),
                "both_ways_learned": Bin.values("both_ways_learned"),
                "serial_control": Bin.values("serial_control"),
            }),
        ),
    ).instantiate("kunminghu_v3.sc.adjacent_feedback")


def write_sc_adjacent_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-adjacent-feedback.json"))


def sc_interleaved_rows_coverage_model():
    return CoverGroupDef(
        "sc_interleaved_rows",
        (
            CoverPointDef("phase", {
                phase: Bin.values(phase)
                for phase in ("cold", "adjacent_learned", "serial_control")
            }),
            CoverPointDef("context", {
                f"row_{index}": Bin.values(index) for index in range(4)
            }),
        ),
        crosses=(CrossDef("phase_by_context", ("phase", "context")),),
    ).instantiate("kunminghu_v3.sc.interleaved_rows")


def write_sc_interleaved_rows_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-interleaved-rows.json"))


def sc_masked_rows_coverage_model():
    return CoverGroupDef(
        "sc_masked_rows",
        (
            CoverPointDef("phase", {
                phase: Bin.values(phase)
                for phase in ("cold", "adjacent_learned", "serial_control")
            }),
            CoverPointDef("context", {f"row_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("way", {f"way_{i}": Bin.values(i) for i in range(SC_WAYS)}),
            CoverPointDef("bias", {f"selector_{i}": Bin.values(i) for i in range(4)}),
        ),
        crosses=(
            CrossDef("phase_by_context_by_way", ("phase", "context", "way")),
            CrossDef("way_by_bias", ("way", "bias")),
        ),
    ).instantiate("kunminghu_v3.sc.masked_rows")


def write_sc_masked_rows_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-masked-rows.json"))


def sc_bias_selector_merge_coverage_model():
    return CoverGroupDef(
        "sc_bias_selector_merge",
        (
            CoverPointDef("mode", {name: Bin.values(name) for name in ("adjacent", "serial")}),
            CoverPointDef("phase", {
                name: Bin.values(name) for name in (
                    "cold", *(f"negative_{i}" for i in range(4)),
                    *(f"positive_{i}" for i in range(4)), "mixed_pipeline",
                )
            }),
            CoverPointDef("row", {f"row_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("bias", {f"selector_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("way", {f"way_{i}": Bin.values(i) for i in range(SC_WAYS)}),
        ),
        crosses=(CrossDef("mode_phase_row_bias_way", ("mode", "phase", "row", "bias", "way")),),
    ).instantiate("kunminghu_v3.sc.bias_selector_merge")


def write_sc_bias_selector_merge_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-bias-selector-merge.json"))


def sc_clean_reactivation_coverage_model():
    return CoverGroupDef(
        "sc_clean_reactivation",
        (
            CoverPointDef("setup", {name: Bin.values(name) for name in ("adjacent", "serial")}),
            CoverPointDef("phase", {
                name: Bin.values(name) for name in (
                    "cold", "queued_learned", *(f"negative_slot_{i}" for i in range(SC_WAYS)),
                    "subset_relearned", "mixed_pipeline",
                )
            }),
            CoverPointDef("row", {f"row_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("bias", {f"selector_{i}": Bin.values(i) for i in range(4)}),
            CoverPointDef("way", {f"way_{i}": Bin.values(i) for i in range(SC_WAYS)}),
        ),
        crosses=(CrossDef("setup_phase_row_bias_way", ("setup", "phase", "row", "bias", "way")),),
    ).instantiate("kunminghu_v3.sc.clean_reactivation")


def write_sc_clean_reactivation_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-clean-reactivation.json"))


def sc_threshold_bounds_coverage_model(mode):
    if mode not in ('single', 'multi'):
        raise ValueError('SC threshold bounds mode must be single or multi')
    return CoverGroupDef(
        f'sc_threshold_{mode}_bounds',
        (
            CoverPointDef('boundary', {name: Bin.values(name) for name in ('lower', 'upper')}),
            CoverPointDef('way', {f'way_{i}': Bin.values(i) for i in range(SC_WAYS)}),
            CoverPointDef('phase', {name: Bin.values(name) for name in ('approach', 'reject', 'recover')}),
        ),
        crosses=(CrossDef('boundary_way_phase', ('boundary', 'way', 'phase')),),
    ).instantiate(f'kunminghu_v3.sc.threshold_{mode}_bounds')


def write_sc_threshold_bounds_coverage(coverage, root, mode):
    if mode not in ('single', 'multi'):
        raise ValueError('SC threshold bounds mode must be single or multi')
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / 'results' / 'sc' / f'functional-coverage-threshold-{mode}-bounds.json'))


def sc_threshold_qualification_coverage_model():
    return CoverGroupDef(
        'sc_threshold_qualification',
        (
            CoverPointDef('way', {f'way_{i}': Bin.values(i) for i in range(SC_WAYS)}),
            CoverPointDef('reason', {name: Bin.values(name) for name in (
                'qualified_wrong', 'mbtb_miss', 'nonconditional', 'provider_invalid',
                'disabled', 'confident_correct', 'net_zero', 'net_positive',
                'net_negative', 'adjacent_burst',
            )}),
        ),
        crosses=(CrossDef('way_reason', ('way', 'reason')),),
    ).instantiate('kunminghu_v3.sc.threshold_qualification')


def write_sc_threshold_qualification_coverage(coverage, root):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / 'results' / 'sc' / 'functional-coverage-threshold-qualification.json'))


def sc_same_way_feedback_coverage_model():
    return CoverGroupDef(
        "sc_same_way_feedback",
        (
            CoverPointDef("phase", {
                "both_qualified": Bin.values("both_qualified"),
                "opposite_cancelled": Bin.values("opposite_cancelled"),
                "single_branch_control": Bin.values("single_branch_control"),
                "both_slots_alias": Bin.values("both_slots_alias"),
            }),
        ),
    ).instantiate("kunminghu_v3.sc.same_way_feedback")


def write_sc_same_way_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-same-way-feedback.json"))


def sc_same_way_double_update_coverage_model():
    return CoverGroupDef(
        "sc_same_way_double_update",
        (
            CoverPointDef("phase", {
                "single_feedback_control": Bin.values("single_feedback_control"),
                "two_branch_feedback": Bin.values("two_branch_feedback"),
                "fewer_accepts": Bin.values("fewer_accepts"),
                "reset_reproducible": Bin.values("reset_reproducible"),
            }),
        ),
    ).instantiate("kunminghu_v3.sc.same_way_double_update")


def write_sc_same_way_double_update_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-same-way-double-update.json"))


def sc_enable_coverage_model():
    return CoverGroupDef(
        "sc_enable",
        (
            CoverPointDef(
                "phase",
                {
                    "trained": Bin.values("trained"),
                    "disabled": Bin.values("disabled"),
                    "retained": Bin.values("retained"),
                    "retrained": Bin.values("retrained"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.sc.enable")


def write_sc_enable_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-enable.json"))


def sc_training_qualification_coverage_model():
    return CoverGroupDef(
        "sc_training_qualification",
        (
            CoverPointDef(
                "phase",
                {
                    "learned_not_taken": Bin.values("learned_not_taken"),
                    "mbtb_miss_ignored": Bin.values("mbtb_miss_ignored"),
                    "nonconditional_ignored": Bin.values("nonconditional_ignored"),
                    "provider_invalid_ignored": Bin.values(
                        "provider_invalid_ignored"
                    ),
                    "qualified_taken_learned": Bin.values(
                        "qualified_taken_learned"
                    ),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.sc.training_qualification")


def write_sc_training_qualification_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "sc" / "functional-coverage-training-qualification.json"))
