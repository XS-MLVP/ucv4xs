"""bpuverify.mbtb.coverage.catalog components."""

from __future__ import annotations

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.common.env.artifacts import output_path
from pathlib import Path
from typing import Any
from toffee import Bin
from toffee import CoverGroupDef
from toffee import CoverPointDef
from toffee import CrossDef
from toffee import CoverageDatabase
from bpuverify.mbtb.model.entry import CARRY_PATTERNS


def mbtb_entry_retarget_coverage_model():
    points = (
        CoverPointDef('context', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('align', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('bank', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('way', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('mode', {value: Bin.values(value) for value in ('blocked', 'flow')}),
        CoverPointDef('pattern', {value: Bin.values(value) for value in CARRY_PATTERNS}),
        CoverPointDef('phase', {value: Bin.values(value) for value in ('prepared', 'updated', 'revisited')}),
    )
    return CoverGroupDef('mbtb_entry_retarget', points,
        crosses=(CrossDef('all_dimensions', tuple(point.name for point in points)),)
    ).instantiate('kunminghu_v3.mbtb.entry_retarget')


def write_mbtb_entry_retarget_coverage(coverage, root):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / 'results/mbtb' / 'functional-coverage-entry-retarget.json'))


def mbtb_entry_keys_coverage_model():
    points = (
        CoverPointDef('context', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('align', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('bank', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('way', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('mode', {value: Bin.values(value) for value in ('blocked', 'flow')}),
        CoverPointDef('order', {value: Bin.values(value) for value in ('first_second', 'second_first')}),
        CoverPointDef('pair', {value: Bin.values(value) for value in CARRY_PATTERNS}),
        CoverPointDef('phase', {value: Bin.values(value) for value in ('prepared', 'updated', 'revisited')}),
    )
    return CoverGroupDef('mbtb_entry_keys', points,
        crosses=(CrossDef('all_dimensions', tuple(point.name for point in points)),)
    ).instantiate('kunminghu_v3.mbtb.entry_keys')


def write_mbtb_entry_keys_coverage(coverage, root):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / 'results/mbtb' / 'functional-coverage-entry-keys.json'))


def mbtb_shadow_coverage_model():
    points = (
        CoverPointDef('context', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('align', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('bank', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('owner', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('phase', {value: Bin.values(value) for value in ('clean_first', 'pending_second')}),
        CoverPointDef('mode', {value: Bin.values(value) for value in ('blocked', 'flow')}),
        CoverPointDef('pattern', {value: Bin.values(value) for value in CARRY_PATTERNS}),
        CoverPointDef('status', {value: Bin.values(value) for value in ('prepared', 'updated', 'revisited')}),
    )
    return CoverGroupDef('mbtb_shadow', points,
        crosses=(CrossDef('all_dimensions', tuple(point.name for point in points)),)
    ).instantiate('kunminghu_v3.mbtb.shadow_routing')


def write_mbtb_shadow_coverage(coverage, root):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / 'results/mbtb' / 'functional-coverage-shadow.json'))


def mbtb_depth_coverage_model():
    points = (
        CoverPointDef('align', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('bank', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('owner', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('phase', {value: Bin.values(value) for value in ('clean_first', 'pending_second')}),
        CoverPointDef('mode', {value: Bin.values(value) for value in ('blocked', 'flow')}),
        CoverPointDef('status', {value: Bin.values(value) for value in ('prepared', 'updated', 'revisited')}),
    )
    return CoverGroupDef('mbtb_depth_one', points,
        crosses=(CrossDef('all_dimensions', tuple(point.name for point in points)),)
    ).instantiate('kunminghu_v3.mbtb.depth_one')


def write_mbtb_depth_coverage(coverage, root):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / 'results/mbtb/functional-coverage-depth-one.json'))


def mbtb_replacement_coverage_model():
    points = (
        CoverPointDef('index', {str(i): Bin.values(i) for i in range(64)}),
        CoverPointDef('align', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('upper', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('mode', {value: Bin.values(value) for value in
                              ('taken_way0', 'taken_way1', 'not_taken', 'lookup_only')}),
        CoverPointDef('phase', {value: Bin.values(value) for value in
                               ('prepared', 'qualified', 'replaced', 'alias_replaced', 'isolated', 'revisited')}),
    )
    return CoverGroupDef('mbtb_replacement', points,
        crosses=(CrossDef('all_dimensions', tuple(point.name for point in points), max_auto_bins=6144),)
    ).instantiate('kunminghu_v3.mbtb.indexed_replacement')


def write_mbtb_replacement_coverage(coverage, root, *, semantic_groups=()):
    write_functional_coverage(CoverageDatabase([coverage, *semantic_groups]), output_path(root / 'results/mbtb' / 'functional-coverage-replacement.json'))


def mbtb_counter_pending_coverage_model():
    points = (
        CoverPointDef('context',{str(i):Bin.values(i) for i in range(2)}),
        CoverPointDef('align',{str(i):Bin.values(i) for i in range(2)}),
        CoverPointDef('bank',{str(i):Bin.values(i) for i in range(2)}),
        CoverPointDef('way',{str(i):Bin.values(i) for i in range(2)}),
        CoverPointDef('taken',{str(i):Bin.values(i) for i in range(2)}),
        CoverPointDef('mode',{value:Bin.values(value) for value in ('blocked','flow')}),
        CoverPointDef('phase',{value:Bin.values(value) for value in ('prepared','updated','revisited')}),
    )
    return CoverGroupDef('mbtb_counter_pending',points,
        crosses=(CrossDef('all_dimensions',tuple(point.name for point in points)),)
    ).instantiate('kunminghu_v3.mbtb.counter_pending')


def write_mbtb_counter_pending_coverage(coverage,root):
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root/'results/mbtb'/'functional-coverage-counter-pending.json'))


def mbtb_coverage_model():
    """MainBTB observations: allocation, coexistence, update, and counter."""

    return CoverGroupDef(
        "mbtb_behavior",
        (
            CoverPointDef(
                "branch_type",
                {
                    "none": Bin.values(0),
                    "conditional": Bin.values(1),
                    "direct": Bin.values(2),
                    "indirect": Bin.values(3),
                },
            ),
            CoverPointDef(
                "occupancy",
                {
                    "empty": Bin.values(0),
                    "single": Bin.values(1),
                    "multiple": Bin.values(2, 3, 4),
                },
            ),
            CoverPointDef(
                "operation",
                {
                    "cold": Bin.values("cold"),
                    "allocate": Bin.values("allocate"),
                    "target_update": Bin.values("target_update"),
                    "counter_train": Bin.values("counter_train"),
                    "cross_page_filter": Bin.values("cross_page_filter"),
                    "prefix_filter": Bin.values("prefix_filter"),
                    "lookup_disabled": Bin.values("lookup_disabled"),
                    "training_disabled": Bin.values("training_disabled"),
                },
            ),
            CoverPointDef(
                "counter",
                {
                    "not_sampled": Bin.values("not_sampled"),
                    "not_taken_saturated": Bin.values("not_taken_saturated"),
                    "taken_saturated": Bin.values("taken_saturated"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.mbtb")


def write_mbtb_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "mbtb" / "functional-coverage.json"))


def mbtb_target_carry_coverage_model():
    return CoverGroupDef(
        "mbtb_target_carry",
        (
            CoverPointDef(
                "case",
                {name: Bin.values(name) for name in ("fit", "overflow", "underflow")},
            ),
        ),
    ).instantiate("kunminghu_v3.mbtb.target_carry")


def write_mbtb_target_carry_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "mbtb" / "functional-coverage-target-carry.json"))


def mbtb_attribute_rewrite_coverage_model():
    return CoverGroupDef(
        "mbtb_attribute_rewrite",
        (
            CoverPointDef(
                "phase",
                {
                    "aged_zero": Bin.values("aged_zero"),
                    "conditional_to_direct": Bin.values("conditional_to_direct"),
                    "direct_to_indirect": Bin.values("direct_to_indirect"),
                    "indirect_to_conditional": Bin.values(
                        "indirect_to_conditional"
                    ),
                    "trained_after_rewrite": Bin.values("trained_after_rewrite"),
                    "neighbor_preserved": Bin.values("neighbor_preserved"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.mbtb.attribute_rewrite")


def write_mbtb_attribute_rewrite_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "mbtb" / "functional-coverage-attribute-rewrite.json"))


def mbtb_correct_feedback_coverage_model():
    return CoverGroupDef(
        "mbtb_correct_feedback",
        (
            CoverPointDef(
                "phase",
                {
                    "initial_weak_positive": Bin.values("initial_weak_positive"),
                    "correct_taken_saturates": Bin.values("correct_taken_saturates"),
                    "mispredict_crosses_negative": Bin.values(
                        "mispredict_crosses_negative"
                    ),
                    "correct_not_taken_ages": Bin.values(
                        "correct_not_taken_ages"
                    ),
                    "correct_not_taken_saturates": Bin.values(
                        "correct_not_taken_saturates"
                    ),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.mbtb.correct_feedback")


def write_mbtb_correct_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "mbtb" / "functional-coverage-correct-feedback.json"))


def mbtb_batch_feedback_coverage_model():
    return CoverGroupDef(
        "mbtb_batch_feedback",
        (
            CoverPointDef(
                "phase",
                {
                    "two_residents": Bin.values("two_residents"),
                    "prepared": Bin.values("prepared"),
                    "slot_one_mispredict": Bin.values("slot_one_mispredict"),
                    "rebalanced": Bin.values("rebalanced"),
                    "both_correct": Bin.values("both_correct"),
                    "saturated": Bin.values("saturated"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.mbtb.batch_feedback")


def write_mbtb_batch_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "mbtb" / "functional-coverage-batch-feedback.json"))


def mbtb_consecutive_feedback_coverage_model():
    return CoverGroupDef(
        "mbtb_consecutive_feedback",
        (
            CoverPointDef(
                "order",
                {
                    "direct_first": Bin.values("direct_first"),
                    "neighbor_first": Bin.values("neighbor_first"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.mbtb.consecutive_feedback")


def write_mbtb_consecutive_feedback_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "mbtb" / "functional-coverage-consecutive-feedback.json"))


def mbtb_overlapping_windows_coverage_model():
    return CoverGroupDef(
        "mbtb_overlapping_windows",
        (
            CoverPointDef(
                "phase",
                {
                    "overlapping_first_window": Bin.values("overlapping_first_window"),
                    "shifted_second_window": Bin.values("shifted_second_window"),
                    "first_window_retained": Bin.values("first_window_retained"),
                },
            ),
        ),
    ).instantiate("kunminghu_v3.mbtb.overlapping_windows")


def write_mbtb_overlapping_windows_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "mbtb" / "functional-coverage-overlapping-windows.json"))


def mbtb_multi_hit_cleanup_coverage_model():
    return CoverGroupDef(
        "mbtb_multi_hit_cleanup",
        (
            CoverPointDef(
                "phase",
                {
                    phase: Bin.values(phase)
                    for phase in (
                        "resident_after_other_set",
                        "public_double_hit",
                        "single_survivor",
                        "other_set_preserved",
                    )
                },
            ),
        ),
    ).instantiate("kunminghu_v3.mbtb.multi_hit_cleanup")


def write_mbtb_multi_hit_cleanup_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / "results" / "mbtb" / "functional-coverage-multi-hit-cleanup.json"))


def mbtb_cleanup_overlap_coverage_model():
    points = (
        CoverPointDef('align', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('bank', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('depth', {str(i): Bin.values(i) for i in range(2)}),
        CoverPointDef('shadow_state', {value: Bin.values(value) for value in ('dirty', 'clean')}),
        CoverPointDef('key', {value: Bin.values(value) for value in ('zero_tag', 'zero_position', 'nonzero')}),
        CoverPointDef('phase', {value: Bin.values(value) for value in ('prepared', 'overlapped', 'revisited')}),
    )
    return CoverGroupDef('mbtb_cleanup_overlap', points,
        crosses=(CrossDef('all_dimensions', tuple(point.name for point in points)),)
    ).instantiate('kunminghu_v3.mbtb.cleanup_overlap')


def write_mbtb_cleanup_overlap_coverage(coverage: Any, root: Path) -> None:
    write_functional_coverage(CoverageDatabase([coverage]), output_path(root / 'results' / 'mbtb' / 'functional-coverage-cleanup-overlap.json'))
