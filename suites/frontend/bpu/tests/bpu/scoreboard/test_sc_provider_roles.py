"""Hand-derived rules for chooser, selector and legal provider transitions."""
from copy import deepcopy
from itertools import product
import pytest
from suites.frontend.bpu.bpu.model.sc.provider_roles import PROFILES
from suites.frontend.bpu.bpu.model.sc.provider_roles import next_feedback
from suites.frontend.bpu.bpu.model.sc.provider_roles import selectors
from suites.frontend.bpu.bpu.model.sc.provider_roles import validate_transition


@pytest.mark.parametrize('profile,expected', (
    ('negative_mid_weak', (0, 2)), ('negative_weak_mid', (2, 0)),
    ('positive_weak_mid', (3, 1)), ('positive_mid_weak', (1, 3))))
def test_bias_selector_hand_vectors(profile, expected):
    assert selectors(PROFILES[profile]) == expected


@pytest.mark.parametrize('profile,counters', tuple(product(PROFILES, product(range(8), repeat=2))))
def test_first_unqualified_counter_chooses_real_feedback(profile, counters):
    goals = PROFILES[profile]
    if counters == goals:
        assert next_feedback(counters, goals) is None
    else:
        lane = 0 if counters[0] != goals[0] else 1
        assert next_feedback(counters, goals) == (lane, int(counters[lane] < goals[lane]))


@pytest.mark.parametrize('lane,value,taken', tuple(product(range(2), range(8), range(2))))
def test_same_provider_saturating_update(lane, value, taken):
    before = [(1, 0, 2), (2, 1, 5)]
    before[lane] = (1, 0, value)
    after = list(before)
    after[lane] = (1, 0, max(0, min(7, value + (1 if taken else -1))))
    assert validate_transition(before, after, lane=lane, taken=taken, mispredict=0) == 'update_same_provider'


@pytest.mark.parametrize('lane,old_table,new_table,taken', tuple(
    (lane, old, new, taken) for lane, taken in product(range(2), repeat=2)
    for old in range(3) for new in range(old + 1, 4)))
def test_allocation_uses_longer_table_and_directional_weak_counter(lane, old_table, new_table, taken):
    before = [(1, 0, 2), (2, 1, 5)]
    before[lane] = (old_table, 0, 2)
    after = list(before)
    after[lane] = (new_table, 1, 4 if taken else 3)
    assert validate_transition(before, after, lane=lane, taken=taken, mispredict=1) == (
        'allocate_weak_positive' if taken else 'allocate_weak_negative')


@pytest.mark.parametrize('fault', ('unchosen', 'bad_delta', 'not_mispredicted', 'shorter_table', 'not_weak'))
def test_illegal_provider_transition_is_rejected(fault):
    before = [(1, 0, 2), (2, 1, 5)]
    after = [(2, 0, 4), (2, 1, 5)]
    mispredict = 1
    if fault == 'unchosen':
        after[1] = (2, 1, 6)
    elif fault == 'bad_delta':
        after[0] = (1, 0, 4)
    elif fault == 'not_mispredicted':
        mispredict = 0
    elif fault == 'shorter_table':
        after[0] = (0, 0, 4)
    else:
        after[0] = (2, 0, 5)
    with pytest.raises(AssertionError):
        validate_transition(before, after, lane=0, taken=1, mispredict=mispredict)
