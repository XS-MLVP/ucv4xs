"""Check address/hash preconditions before using the DUT."""
import pytest
from suites.frontend.bpu.bpu.model.phr.model import path_hash
from suites.frontend.bpu.bpu.case.bypass.force_plan import second_key
from suites.frontend.bpu.bpu.case.bypass.force_plan import upper_full_tag
from suites.frontend.bpu.bpu.case.bypass.lower_plan import recipe


@pytest.mark.parametrize('edge', range(4))
def test_second_loop_edges_preserve_complete_zero_history(edge):
    pc, position, target = second_key()['edges'][edge]
    assert path_hash((pc & ~7) + position, target) == 0


def test_second_loop_has_distinct_actual_RTL_index_and_same_bank():
    first, second = recipe(), second_key()
    assert first['a'] & 511 == 0 and second['a'] & 511 == 128
    assert {pc % 4 for pc in (first['a'], first['b'], first['c'], second['a'], second['b'], second['c'])} == {0}
    assert second['expected_lower_full_tag'] == 2080


def test_cold_checkpoint_program_counters_are_distinct_before_any_training():
    first, second = recipe(), second_key()
    pcs = [item[key] for item in (first, second) for key in ('a', 'b', 'c')]
    assert len(set(pcs)) == 6 and all(pc % 8 == 0 for pc in pcs)


def test_cold_checkpoint_scan_reaches_all_leads_in_increasing_order():
    from suites.frontend.bpu.bpu.case.bypass.force_seed import checkpoint_program_counters
    from suites.frontend.bpu.bpu.case.sc.role_scenarios import source_pc
    first, second = recipe(), second_key()
    pcs = checkpoint_program_counters(first['a'], first['b'], first['c'],
        (second['a'], second['b'], second['c']))
    leads = [source_pc(pc) - 8 for pc in pcs]
    assert len(set(pcs)) == 6 and all(pc % 16 == 0 for pc in leads)
    assert all(left < right for left, right in zip(leads, leads[1:]))


def test_append_order_regression_would_ask_for_a_PC_already_passed():
    first, second = recipe(), second_key()
    old_order = [item[key] for item in (first, second) for key in ('a', 'b', 'c')]
    assert old_order[2] > old_order[3]


def test_upper_full_tag_is_representable_before_invoking_DUT():
    assert upper_full_tag(second_key()['a']) == 0
    assert second_key()['expected_upper_full_tag'] < 256


def test_previous_position1_PC_cannot_hit_either_stored_tag():
    from suites.frontend.bpu.bpu.case.bypass.lower_plan import lower_full_tag
    assert lower_full_tag(0x40010420) == 1040
    assert upper_full_tag(0x40010420) == 2336


@pytest.mark.parametrize('valid,position,counter,expected', ((0,0,7,0),(1,4,7,0),(1,0,7,1),(1,0,0,1)))
def test_public_qualification_filters_valid_position_not_correctness(valid, position, counter, expected):
    from types import SimpleNamespace
    from suites.frontend.bpu.bpu.case.bypass.force_second_key import conditional_slots
    entry = dict(valid=valid, cfiPosition=position, takenCtr_value=counter)
    actual = SimpleNamespace(meta=SimpleNamespace(resolve={'utage': {'abtbResult': [entry]}}))
    assert len(conditional_slots(actual, 0)) == expected


def _multi_hit_fixture():
    from copy import deepcopy
    source = dict(valid=1, entries=[dict(hit=int(way in (0, 3)), position=0,
        attribute=dict(branchType=1, rasAction=0)) for way in range(4)])
    valid = dict(valid=1, hit=1, tableId=1, cfiPosition=0, takenCtr_value=7, predTaken=1)
    invalid = dict(valid=0, hit=0, tableId=0, cfiPosition=0, takenCtr_value=0, predTaken=0)
    actual = dict(prediction=dict(start_pc=0x40010000, target=0x40010000, taken=1, position=0),
        meta=dict(resolve=dict(utage=dict(readIndex=[0, 0],
            abtbResult=[deepcopy(valid if way in (0, 3) else invalid) for way in range(4)]))))
    return actual, source, dict(data_valid=1, tag=0, position=0, counter=7)


def _check_multi_hit(actual, source, payload):
    from suites.frontend.bpu.bpu.case.bypass.public_readback import public_readback_pair
    from toffee import Scoreboard
    expected, observed = public_readback_pair(actual, source, payload,
        pc=0x40010000, index=0, position=0)
    Scoreboard('pure.every_public_way').check(expected=expected, actual=observed)


def test_transient_multi_hit_checks_both_correct_public_ways():
    _check_multi_hit(*_multi_hit_fixture())


@pytest.mark.parametrize('way', (0, 3))
@pytest.mark.parametrize('field', ('valid', 'hit', 'tableId', 'cfiPosition', 'takenCtr_value', 'predTaken'))
def test_wrong_first_or_second_duplicate_way_is_not_filtered(way, field):
    from toffee import ScoreboardMismatch
    actual, source, payload = _multi_hit_fixture()
    actual['meta']['resolve']['utage']['abtbResult'][way][field] ^= 1
    with pytest.raises(ScoreboardMismatch):
        _check_multi_hit(actual, source, payload)


@pytest.mark.parametrize('field', ('start_pc', 'target', 'taken', 'position'))
def test_public_prediction_after_SRAM_readback_is_checked(field):
    from toffee import ScoreboardMismatch
    actual, source, payload = _multi_hit_fixture()
    actual['prediction'][field] ^= 1
    with pytest.raises(ScoreboardMismatch):
        _check_multi_hit(actual, source, payload)


def test_public_read_index_is_checked_from_real_old_key():
    from toffee import ScoreboardMismatch
    actual, source, payload = _multi_hit_fixture()
    actual['meta']['resolve']['utage']['readIndex'][1] ^= 1
    with pytest.raises(ScoreboardMismatch):
        _check_multi_hit(actual, source, payload)


def test_missing_public_way_is_not_hidden_by_projection():
    from toffee import ScoreboardMismatch
    actual, source, payload = _multi_hit_fixture()
    actual['meta']['resolve']['utage']['abtbResult'].pop()
    with pytest.raises(ScoreboardMismatch):
        _check_multi_hit(actual, source, payload)
