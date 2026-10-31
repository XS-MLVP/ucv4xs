"""Threshold policy is checked independently of hardware observations."""
from dataclasses import replace

import pytest

from suites.frontend.bpu.sc.transaction.types import ScBatchTraining
from suites.frontend.bpu.sc.transaction.types import ScBranchFeedback
from suites.frontend.bpu.sc.model.threshold import ScThresholdModel


def feedback(*outcomes, positions=(0, 9, 18, 27), **meta_changes):
    meta = {key: (value,) * 10 for key, value in (
        ('scPred', 1), ('tagePred', 1), ('tagePredValid', 1),
        ('useScPred', 0), ('sumAboveThres', 0),
    )}
    meta.update(meta_changes)
    return ScBatchTraining(0x40000040, meta, tuple(
        ScBranchFeedback(positions[slot], taken, slot)
        for slot, taken in enumerate(outcomes)
    ))


@pytest.mark.parametrize('way, positions', [(way, tuple((i<<3)|(way^i) for i in range(4))) for way in range(8)])
def test_position_hash_uses_three_and_two_bit_chunks(way, positions):
    assert tuple(ScThresholdModel().way(pos) for pos in positions) == (way,) * 4


@pytest.mark.parametrize('outcomes, delta, inc, dec', [
    ((0, 0, 0, 0), 4, 4, 0), ((1, 1, 1, 1), -4, 0, 4),
    ((0, 1), 0, 1, 1), ((0, 0, 1), 1, 2, 1), ((1, 1, 0), -1, 1, 2),
])
def test_same_way_branches_aggregate_before_one_update(outcomes, delta, inc, dec):
    update = ScThresholdModel().apply(feedback(*outcomes))
    assert update.after == (1130 + delta, *([1130]*7))
    assert update.increments == (inc, *([0]*7))
    assert update.decrements == (dec, *([0]*7))
    assert update.qualifying_slots == tuple(range(len(outcomes)))
    assert update.rejected_ways == ()


@pytest.mark.parametrize('initial, outcomes', [(834, (1,) * 4), (8062, (0,) * 4)])
def test_out_of_range_aggregate_keeps_old_value_not_nearest_endpoint(initial, outcomes):
    model = ScThresholdModel(initial=(initial, *([1130]*7)))
    update = model.apply(feedback(*outcomes))
    assert update.after == update.before == (initial, *([1130]*7))
    assert update.rejected_ways == (0,)


@pytest.mark.parametrize('initial, outcome, final', [(833, 1, 832), (8063, 0, 8064)])
def test_boundary_is_inclusive_then_rejects_and_can_recover(initial, outcome, final):
    model = ScThresholdModel(initial=initial)
    assert model.apply(feedback(outcome)).after[0] == final
    assert model.apply(feedback(outcome)).rejected_ways == (0,)
    assert model.apply(feedback(1 - outcome)).after[0] == initial
    model.reset()
    assert model.values == (initial,) * 8


@pytest.mark.parametrize('changes', [
    {'tagePredValid': (0,) * 10},
    {'useScPred': (1,) * 10},
    {'sumAboveThres': (1,) * 10},
])
def test_correct_feedback_is_suppressed_by_valid_use_or_confidence(changes):
    update = ScThresholdModel().apply(feedback(1, **changes))
    assert update.after == update.before
    assert update.qualifying_slots == ()


def test_correct_disagreement_with_tage_can_decrease_below_threshold():
    update = ScThresholdModel().apply(feedback(1, useScPred=(1,) * 10, tagePred=(0,) * 10))
    assert update.after == (1129, *([1130]*7))


def test_wrong_high_confidence_feedback_still_increases():
    update = ScThresholdModel().apply(feedback(0, useScPred=(1,) * 10, sumAboveThres=(1,) * 10))
    assert update.after == (1131, *([1130]*7))


@pytest.mark.parametrize('branch_changes, enabled', [
    ({'mbtb_hit': 0}, True), ({'branch_type': 2}, True), ({}, False),
])
def test_training_qualification_preserves_all_ways(branch_changes, enabled):
    beat = feedback(0)
    beat = replace(beat, branches=(replace(beat.branches[0], **branch_changes),))
    update = ScThresholdModel().apply(beat, enabled=enabled)
    assert update.after == update.before
    assert update.qualifying_slots == ()


def test_sparse_resolve_slot_uses_prediction_slot_not_resolve_index():
    beat = feedback(0, positions=(3,))
    beat = replace(beat, branches=(None, None, replace(beat.branches[0], prediction_slot=2)))
    assert ScThresholdModel().apply(beat).after == (1130, 1130, 1130, 1131, 1130, 1130, 1130, 1130)


@pytest.mark.parametrize('initial, outcome, final', [(0, 1, 0), (8191, 0, 8191)])
def test_raw_unsigned_counter_saturates_before_custom_range_check(initial, outcome, final):
    model = ScThresholdModel(minimum=0, maximum=8191, initial=initial)
    update = model.apply(feedback(outcome))
    assert update.after[0] == final
    assert update.rejected_ways == ()


@pytest.mark.parametrize('changes', [
    {'ways': 1}, {'ways': 3}, {'width': 0}, {'position_width': 0},
    {'minimum': -1}, {'maximum': 8192}, {'minimum': 8065},
    {'initial': 831}, {'initial': (1130,)},
])
def test_bad_geometry_is_rejected(changes):
    with pytest.raises(ValueError):
        ScThresholdModel(**changes)


@pytest.mark.parametrize('branch_changes', [
    {'position': -1}, {'position': 32}, {'actual_taken': 2},
    {'mbtb_hit': 2}, {'branch_type': 4}, {'prediction_slot': 10},
])
def test_bad_later_branch_cannot_partially_update_reference(branch_changes):
    model = ScThresholdModel()
    beat = feedback(0, 0)
    beat = replace(beat, branches=(beat.branches[0], replace(beat.branches[1], **branch_changes)))
    with pytest.raises(ValueError):
        model.apply(beat)
    assert model.values == (1130,) * 8


def test_invalid_metadata_and_later_burst_leave_reference_unchanged():
    model = ScThresholdModel()
    invalid = feedback(0, scPred=(2,) * 10)
    with pytest.raises(ValueError):
        model.apply_many((feedback(0), invalid))
    assert model.values == (1130,) * 8
    with pytest.raises(ValueError, match='empty'):
        model.apply_many(())
    with pytest.raises(ValueError, match='per prediction slot'):
        model.apply(feedback(0, scPred=(1,)))
    assert model.values == (1130,) * 8
