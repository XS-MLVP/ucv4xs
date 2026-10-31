"""Input expectations must not share the driver's encoding implementation."""
from dataclasses import replace

import pytest

from suites.frontend.bpu.tage.transaction.types import TageBatchTraining
from suites.frontend.bpu.tage.transaction.types import TageBranchFeedback
from suites.frontend.bpu.tage.driver.feedback import expected_tage_feedback
from suites.frontend.bpu.tage.driver.feedback import observed_tage_feedback


def branch(position=6, **changes):
    return replace(TageBranchFeedback(position, 1, 0, {'provider': position}), **changes)


@pytest.mark.parametrize('slot', range(8))
def test_sparse_resolve_placement_does_not_choose_the_prediction_meta_index(slot):
    item = branch()
    beat = TageBatchTraining(0x40000000, (None,) * slot + (item,))
    expected = expected_tage_feedback(beat)
    assert len(expected['resolved']) == 8
    assert tuple(i for i, value in enumerate(expected['resolved']) if value is not None) == (slot,)
    assert expected['prediction_entries'] == ({'position': 6, 'branch_type': 1,
                                               'base_counter': 1, 'meta': item.meta},)


def test_metadata_is_frozen_before_the_request_can_be_changed():
    item = branch()
    expected = expected_tage_feedback(TageBatchTraining(0x40000000, (item,)))
    item.meta['provider'] = 99
    assert expected['prediction_entries'][0]['meta'] == {'provider': 6}


def test_inactive_and_unmatched_branches_do_not_consume_prediction_slots():
    beat = TageBatchTraining(0x40000000, (
        branch(1, valid=0), branch(2, mbtb_hit=0), None, branch(6),
    ))
    expected = expected_tage_feedback(beat)
    assert expected['resolved'][0] is None
    assert expected['resolved'][1]['position'] == 2
    assert len(expected['prediction_entries']) == 1
    assert expected['prediction_entries'][0]['position'] == 6


@pytest.mark.parametrize('base, counter', [(0, 0), (0, 1), (1, 2), (1, 3)])
def test_base_counter_and_metadata_remain_associated(base, counter):
    expected = expected_tage_feedback(TageBatchTraining(0x40000000, (
        branch(1, base_taken=base, base_counter_value=counter), None, branch(6),
    )))
    assert tuple(entry['position'] for entry in expected['prediction_entries']) == (1, 6)
    assert expected['prediction_entries'][0]['base_counter'] == counter


@pytest.mark.parametrize('branches', [(), (None,), (branch(),) * 9])
def test_bad_resolve_shape_is_rejected(branches):
    with pytest.raises(ValueError):
        expected_tage_feedback(TageBatchTraining(0x40000000, branches))


@pytest.mark.parametrize('counter', [-1, 2, 4])
def test_bad_base_counter_is_rejected(counter):
    with pytest.raises(ValueError):
        expected_tage_feedback(TageBatchTraining(0x40000000, (branch(base_counter_value=counter),)))


def test_observer_uses_banked_raw_hit_meta_mapping_and_ignores_invalid_bits():
    sample = {'ready': 1, 'bits': {'start_pc': 0x40000000,
        'branches': ({'valid': 0, 'position': 99},
                     {'valid': 1, 'position': 6, 'taken': 1, 'branch_type': 1, 'mispredict': 0}),
        'mbtb_meta': (({'rawHit': 0},), ({'rawHit': 1, 'position': 6,
                                         'attribute': {'branchType': 1}, 'counter_value': 1},)),
        'tage_meta': ({'provider': 99}, {'provider': 6})}}
    actual = observed_tage_feedback(sample)
    expected = expected_tage_feedback(TageBatchTraining(0x40000000, (None, branch())), branch_count=2)
    assert actual == expected
