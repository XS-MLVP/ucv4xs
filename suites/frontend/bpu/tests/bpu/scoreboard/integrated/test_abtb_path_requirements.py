"""A successful scene must still prove every required physical path."""
import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.bpu.case.abtb.requirements import required_counter_paths
from suites.frontend.bpu.bpu.case.abtb.requirements import require_counter_paths

CAUSES = ('same_position_taken', 'final_not_taken', 'later_taken')
ALL_LABELS = required_counter_paths(bank=1, entry_set=1, causes=CAUSES)


def test_geometry_is_all256_groups_times_four_ways_times_twelve_paths():
    all_labels = set()
    for bank in range(4):
        for entry_set in range(64):
            labels = required_counter_paths(bank=bank, entry_set=entry_set, causes=CAUSES)
            assert len(labels) == len(set(labels)) == 48
            all_labels.update(labels)
    assert len(all_labels) == 12288


def test_finalNT_requires_all32_increment_decrement_and_hold_paths():
    labels = required_counter_paths(bank=1, entry_set=1, causes=CAUSES[:2])
    result = require_counter_paths(dict(transition_counts=dict.fromkeys(labels, 1)),
                                  bank=1, entry_set=1, causes=CAUSES[:2])
    assert result == dict(required_paths=32, covered_paths=32, bank=1, entry_set=1,
                          ways=4, causes=CAUSES[:2])
    assert all(any(f'.way{way}.' in label and label.endswith(path) for label in labels)
               for way in range(4) for path in ('inc3_3', 'dec0_0'))


@pytest.mark.parametrize('missing', ALL_LABELS)
def test_missing_one_specific_way_path_cannot_be_hidden_by_other_counts(missing):
    counts = dict.fromkeys(ALL_LABELS, 100000)
    del counts[missing]
    with pytest.raises(ScoreboardMismatch) as caught:
        require_counter_paths(dict(transition_counts=counts), bank=1, entry_set=1, causes=CAUSES)
    error = caught.value
    assert missing in str(error)
    assert error.context.request['bank'] == 1
    assert error.context.request['entry_set'] == 1
    assert error.context.request['observed_counts'][missing] == 0
    assert error.status.failed == 1


def test_old18_of32_shape_fails_even_when_scene_itself_passed():
    labels = required_counter_paths(bank=1, entry_set=1, causes=CAUSES[:2])
    counts = {label: 100 for label in labels if '.way2.' in label or '.way3.' in label
              or label.endswith('inc2_3')}
    assert len(counts) == 18
    with pytest.raises(ScoreboardMismatch):
        require_counter_paths(dict(passed=True, transition_counts=counts),
                              bank=1, entry_set=1, causes=CAUSES[:2])


@pytest.mark.parametrize('bank,entry_set', ((True, 0), (0, True), (-1, 0), (4, 0), (0, -1), (0, 64), (1.0, 1)))
def test_invalid_coordinate_rejected(bank, entry_set):
    with pytest.raises(ValueError):
        required_counter_paths(bank=bank, entry_set=entry_set, causes=CAUSES)


@pytest.mark.parametrize('causes', ((), [], 'final_not_taken', ('wrong',), ('final_not_taken', 'final_not_taken'), (None,)))
def test_invalid_requirement_rejected(causes):
    with pytest.raises(ValueError):
        required_counter_paths(bank=0, entry_set=0, causes=causes)


@pytest.mark.parametrize('summary', (None, {}, {'transition_counts': []}))
def test_missing_checked_counts_rejected(summary):
    with pytest.raises(ValueError):
        require_counter_paths(summary, bank=1, entry_set=1, causes=CAUSES)


@pytest.mark.parametrize('bad', (-1, True, 1.0, '1', None))
def test_invalid_count_rejected(bad):
    counts = dict.fromkeys(ALL_LABELS, 1)
    counts[ALL_LABELS[0]] = bad
    with pytest.raises(ValueError):
        require_counter_paths(dict(transition_counts=counts), bank=1, entry_set=1, causes=CAUSES)
