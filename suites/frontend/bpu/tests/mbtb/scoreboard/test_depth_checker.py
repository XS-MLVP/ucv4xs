"""Undefined payload normalization must not hide any defined neighbor field."""
from copy import deepcopy
from dataclasses import replace

import pytest

from suites.frontend.bpu.mbtb.checker.depth import defined_depth_check, defined_depth_profile
from suites.frontend.bpu.mbtb.case.resident_scenario import frozen_check
from suites.frontend.bpu.mbtb.transaction.types import MbtbPrediction
from tests.mbtb.scoreboard.test_depth_model import prepared
from tests.mbtb.scoreboard.test_depth_owner import with_peer


def prediction(profile):
    return MbtbPrediction(deepcopy(profile['entries']), deepcopy(profile['meta_entries']))


def test_only_unmatched_invalid_payload_can_vary_and_generic_checker_stays_strict():
    wanted = prepared(0, 1, 0)[1]
    actual = prediction(wanted)
    entries = list(actual.entries)
    entries[0] = replace(entries[0], taken=1, target=0xDEAD, position=15, branch_type=3, ras_action=2)
    metadata = deepcopy(actual.meta_entries)
    metadata[0][0].update(counter_value=3, position=15, attribute=dict(branchType=3, rasAction=2))
    actual = replace(actual, entries=tuple(entries), meta_entries=metadata)
    defined_depth_check(wanted)(actual)
    with pytest.raises(AssertionError):
        frozen_check(wanted)(actual)


@pytest.mark.parametrize('field', ('valid', 'taken', 'target', 'position', 'branch_type', 'ras_action'))
def test_every_visible_neighbor_field_is_still_compared(field):
    wanted = with_peer(0)[1]
    actual = prediction(wanted)
    peer = actual.entries[0]
    entries = (replace(peer, **{field: getattr(peer, field) ^ 1}), *actual.entries[1:])
    with pytest.raises(AssertionError, match='mbtb.depth-defined-consumer'):
        defined_depth_check(wanted)(replace(actual, entries=entries))


@pytest.mark.parametrize('filtered', (False, True))
@pytest.mark.parametrize('field', ('rawHit', 'counter_value', 'position', 'branchType', 'rasAction'))
def test_all_hit_metadata_is_checked_even_when_public_prediction_is_filtered(filtered, field):
    wanted = with_peer(0, filtered=filtered)[1]
    actual = prediction(wanted)
    meta = actual.meta_entries[0][0]
    if field in ('branchType', 'rasAction'):
        meta['attribute'][field] ^= 1
    else:
        meta[field] ^= 1
    with pytest.raises(AssertionError, match='mbtb.depth-defined-consumer'):
        defined_depth_check(wanted)(actual)


@pytest.mark.parametrize('which', ('prediction-valid', 'raw-hit'))
def test_unmatched_slot_cannot_silently_acquire_validity_or_training_permission(which):
    wanted = prepared(0, 1, 0)[1]
    actual = prediction(wanted)
    if which == 'prediction-valid':
        actual = replace(actual, entries=(replace(actual.entries[0], valid=1), *actual.entries[1:]))
    else:
        actual.meta_entries[0][0]['rawHit'] = 1
    with pytest.raises(AssertionError):
        defined_depth_check(wanted)(actual)


def test_expected_is_frozen_before_later_caller_mutation_and_never_resynchronized():
    wanted = with_peer(3)[1]
    original = deepcopy(wanted)
    check = defined_depth_check(wanted)
    wanted['entries'] = (replace(wanted['entries'][0], target=0x1234), *wanted['entries'][1:])
    wanted['meta_entries'][0][0]['counter_value'] = 2
    check(prediction(original))
    with pytest.raises(AssertionError):
        check(prediction(wanted))
    check(prediction(original))


def test_filtered_payload_may_change_but_its_counter_remains_a_defined_source():
    wanted = with_peer(0, filtered=True)[1]
    actual = prediction(wanted)
    actual = replace(actual, entries=(replace(actual.entries[0], target=0x1234, taken=1), *actual.entries[1:]))
    check = defined_depth_check(wanted)
    check(actual)
    actual.meta_entries[0][0]['counter_value'] = 2
    with pytest.raises(AssertionError):
        check(actual)


@pytest.mark.parametrize('profile', (dict(entries=(), meta_entries=()), dict(entries=(1,) * 4, meta_entries=((), ()))))
def test_incomplete_shape_cannot_turn_into_an_empty_success(profile):
    with pytest.raises(ValueError, match='two alignments'):
        defined_depth_profile(profile)
