from copy import deepcopy
from pathlib import Path
import pytest
from bpuverify.abtb.model.state.counter import CounterReference
from bpuverify.abtb.model.state.counter import index
from bpuverify.bpu.model.phr.model import folds
from bpuverify.bpu.model.abtb.final_not_taken import ALL_CASES
from bpuverify.bpu.model.abtb.final_not_taken import PHASES
from bpuverify.bpu.model.abtb.final_not_taken import capacity
from bpuverify.bpu.model.abtb.final_not_taken import fall_through
from bpuverify.bpu.model.abtb.final_not_taken import joint_reference
from bpuverify.bpu.model.abtb.final_not_taken import nonzero_violations
from bpuverify.bpu.model.abtb.final_not_taken import plan
from bpuverify.bpu.model.abtb.final_not_taken import scalar_proof
from bpuverify.bpu.model.abtb.alias import physical_index


@pytest.mark.parametrize('bank,entry_set', ALL_CASES)
def test_all_coordinates_have_real_final_NT_fallthrough_and_same_target_index(bank, entry_set):
    intent = plan(bank, entry_set)
    assert len(intent['cycles']) == 5 and len(intent['branch_programs']) == 20
    assert len({pc for triple in intent['cycles'] for pc in triple}) == 20
    assert max(capacity(intent['cycles']).values()) <= 2
    for a, b, c, d in intent['cycles']:
        assert fall_through(a)['target'] == b and fall_through(a)['taken'] == 0
        assert physical_index(d, intent['low4_index_source_history']) == bank + entry_set * 4
    assert not nonzero_violations(intent['cycles'])
    result = scalar_proof(intent)
    assert result['scalar_full52_checks'] == 960
    assert result['target_index_checks'] == 235


@pytest.mark.parametrize('bank,entry_set', ALL_CASES)
def test_all_coordinates_joint_full_PHR_and_pipeline_index_reference(bank, entry_set):
    result = joint_reference(plan(bank, entry_set))
    assert result['full52_reference_checks'] == 960
    assert result['joint_index_checks'] == 950
    assert result['final_NT_history_and_pointer_holds'] == 80


@pytest.mark.parametrize('bank,entry_set', [(0, 0), (1, 0), (2, 31), (3, 63)])
def test_held_cycles_preserve_complete_reference(bank, entry_set):
    result = joint_reference(plan(bank, entry_set), idle_cycles=2)
    assert result['full52_reference_checks'] == 2880
    assert result['joint_index_checks'] == 950
    assert result['final_NT_history_and_pointer_holds'] == 80


def test_geometric_fallthrough_matches_literal_generated_RTL_for_two_pages():
    for addr in range(4096):
        raw = (addr << 1) + 32
        same_page = ((addr >> 11) & 1) == ((raw >> 12) & 1)
        target = (raw >> 4) << 3 if same_page else (raw >> 12) << 11
        position = 15 if same_page else ((1 - ((raw >> 4) & 1)) << 3) | 7
        actual = fall_through(addr)
        assert actual['target'] == target and actual['position'] == position
        assert actual['cross_page'] == (not same_page)
        assert 7 <= position <= 15


def test_page_crossing_is_not_unconditionally_plus16_halfwords():
    assert fall_through(0xff0 >> 1)['target'] == 0x1000 >> 1
    assert fall_through(0xff0 >> 1)['position'] == 7
    assert fall_through(0xfe0 >> 1)['position'] == 15
    assert fall_through(0x100 >> 1)['target'] == 0x120 >> 1
    assert fall_through((0x100 >> 1) + 6)['target'] == 0x120 >> 1


@pytest.mark.parametrize('bank,entry_set', [(-1, 0), (4, 0), (True, 0), ('0', 0),
    (0, -1), (0, 64), (0, True), (0, '0')])
def test_invalid_coordinates_rejected(bank, entry_set):
    with pytest.raises(ValueError):
        plan(bank, entry_set)


@pytest.mark.parametrize('addr', [-1, True, 1.5, '0', (1 << 49) - 16, 1 << 49])
def test_unsupported_or_overflowing_halfword_address_rejected(addr):
    with pytest.raises(ValueError):
        fall_through(addr)


@pytest.mark.parametrize('rounds', [0, 13, True, 1.5])
def test_short_or_invalid_flush_rounds_rejected(rounds):
    with pytest.raises(ValueError):
        scalar_proof(plan(0, 0), rounds)


@pytest.mark.parametrize('idle', [-1, 9, True, 1.5])
def test_invalid_idle_rejected(idle):
    with pytest.raises(ValueError):
        joint_reference(plan(0, 0), idle)


def test_low_index_fold_is_checked_against_full_fold_layout():
    for history in (0, 1, 3, 63, 64, (1 << 52) - 1, 0x123456789abcd):
        assert folds(history)[2] == history & 63


def feedback(way, *, taken, final_position):
    entries = [dict(hit=0, position=0, attribute=dict(branchType=0, rasAction=0)) for _ in range(4)]
    entries[way] = dict(hit=1, position=6, attribute=dict(branchType=1, rasAction=0))
    entries[(way + 1) % 4] = dict(hit=1, position=7, attribute=dict(branchType=3, rasAction=0))
    return dict(meta=dict(bankMask=1, setIdx=0, entries=entries), pc=0x40011070,
        taken=taken, position=final_position, branch_type=3 if taken else 0, ras_action=0)


def step_and_drain(model, tx):
    model.advance(reset=0, accepted=tx, writes=[])
    result = model.advance(reset=0, accepted=None, writes=[])
    model.advance(reset=0, accepted=None, writes=[])
    return result


@pytest.mark.parametrize('way', range(4))
@pytest.mark.parametrize('before', range(4))
def test_final_not_taken_decreases_conditional_without_taken_PLRU_touch(way, before):
    model = CounterReference()
    model.advance(reset=0, accepted=None,
        writes=[dict(bank=0, set_index=0, way=way, reset_counter=True)])
    for _ in range(abs(before - 2)):
        taken = int(before > 2)
        tx = feedback(way, taken=taken, final_position=6)
        if taken:
            tx['branch_type'] = 1
        step_and_drain(model, tx)
    assert model.cells[index(0, 0, way)] == before
    old_plru = deepcopy(model.plru)
    transitions = step_and_drain(model, feedback(way, taken=0, final_position=15))
    assert len(transitions) == 1
    assert transitions[0]['transition'] == f'dec{before}_{max(0, before - 1)}'
    assert transitions[0]['feedback']['taken'] == 0
    assert model.plru == old_plru and model.pending1 is model.pending2 is None


@pytest.mark.parametrize('way', range(4))
def test_later_taken_is_a_distinct_decrease_path_with_matching_taken_entry_touch(way):
    model = CounterReference()
    model.advance(reset=0, accepted=None,
        writes=[dict(bank=0, set_index=0, way=way, reset_counter=True)])
    # Use all initial states to ensure the touched final entry is observable.
    from bpuverify.abtb.model.state.counter import touch
    old = model.plru[0][0]
    transitions = step_and_drain(model, feedback(way, taken=1, final_position=7))
    assert transitions[0]['transition'] == 'dec2_1'
    assert transitions[0]['feedback']['taken'] == 1
    assert model.plru[0][0] == touch(old, (way + 1) % 4)


def test_all_eight_counter_transitions_and_no_fallback_resident_are_required():
    assert {name for _, _, required in PHASES for name in required} == {
        'inc0_1', 'inc1_2', 'inc2_3', 'inc3_3', 'dec3_2', 'dec2_1', 'dec1_0', 'dec0_0'}
    intent = plan(3, 63)
    for a, _, _, _ in intent['cycles']:
        assert len([row for row in intent['branch_programs'] if row['pc'] == a]) == 1


def test_three_node_current_request_cannot_be_used_as_current_A_metadata():
    from bpuverify.bpu.model.abtb.index import IndexReference
    from bpuverify.bpu.model.abtb.index import control
    model=IndexReference()
    model.advance(**control(reset=1,tick=0))
    targets=(0x110,0x220,0x330)
    for beat in range(9):
        if beat>=3 and beat%3==0:
            assert model.s2['pc']==targets[(beat-2)%3]
            assert model.s2['pc']!=targets[beat%3]
        model.advance(**control(pc=targets[beat%3],folded6=beat&63,tick=beat+1))
