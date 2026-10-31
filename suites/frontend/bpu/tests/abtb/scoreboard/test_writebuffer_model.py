from copy import deepcopy
from itertools import permutations
import pytest
from suites.frontend.bpu.abtb.model.state.writebuffer import WriteBufferReference
from suites.frontend.bpu.abtb.model.state.writebuffer import CapacityReference
from suites.frontend.bpu.abtb.model.state.writebuffer import zero


def request(s, *, target=0x90000):
    return dict(need_reset=1, set_index=s, way=0, valid=1, tag=0x800 + s * 2,
                position=1, branch_type=1, ras_action=0, target_low=target + s * 0x100)


def filled(sets=(5, 6, 7, 8)):
    reference = WriteBufferReference()
    for i, s in enumerate(sets):
        drain, event = reference.advance(reset=0, write=request(s), ready=0)
        assert drain is None and event['slot'] == i and event['role'] == 'free_slot'
    return reference


@pytest.mark.parametrize('sets', tuple(permutations((5, 6, 7, 8))))
def test_four_distinct_sets_fill_and_drain_in_physical_order(sets):
    reference = filled(sets)
    assert [slot['dirty'] for slot in reference.slots] == [1] * 4
    for i, s in enumerate(sets):
        drain, event = reference.advance(reset=0, write=None, ready=1)
        assert drain == dict(slot=i, payload=request(s)) and event is None
    assert [slot['dirty'] for slot in reference.slots] == [0] * 4
    assert [slot['shadow_valid'] for slot in reference.slots] == [1] * 4
    assert reference.advance(reset=0, write=None, ready=1) == (None, None)


@pytest.mark.parametrize('slot', range(4))
@pytest.mark.parametrize('ready', (0, 1))
def test_dirty_update_and_drain_priority_from_same_prestate(slot, ready):
    reference = filled()
    before, state = deepcopy(reference.slots), reference.plru
    payload = request(5 + slot, target=0xa0000)
    drain, event = reference.advance(reset=0, write=payload, ready=ready)
    assert event['slot'] == slot and event['role'] == 'dirty_hit'
    assert reference.slots[slot] == dict(shadow_valid=1, dirty=1, payload=payload)
    assert reference.plru == state
    if ready:
        assert drain == dict(slot=0, payload=before[0]['payload'])
        assert reference.slots[0]['dirty'] == int(slot == 0)
    else:
        assert drain is None


@pytest.mark.parametrize('slot', range(4))
@pytest.mark.parametrize('changed', (False, True))
def test_clean_payload_same_or_changed(slot, changed):
    reference = filled()
    for _ in range(4):
        reference.advance(reset=0, write=None, ready=1)
    payload = request(5 + slot, target=0xa0000 if changed else 0x90000)
    _, event = reference.advance(reset=0, write=payload, ready=0)
    assert event['role'] == ('clean_changed' if changed else 'clean_same')
    assert [state['dirty'] for state in reference.slots] == [int(changed and i == slot) for i in range(4)]
    assert reference.slots[slot]['payload'] == payload


@pytest.mark.parametrize('slot', range(4))
def test_same_set_new_tag_prefers_retained_slot_over_empty_or_plru(slot):
    reference = filled()
    reference.plru = 0
    payload = dict(request(5 + slot), tag=0x888888)
    _, event = reference.advance(reset=0, write=payload, ready=0)
    assert event['slot'] == slot and event['role'] == 'same_set_replace'


@pytest.mark.parametrize('state,expected', tuple(enumerate((0, 1, 0, 1, 2, 2, 3, 3))))
def test_full_miss_overwrites_independent_plru_victim(state, expected):
    reference = filled()
    reference.plru = state
    _, event = reference.advance(reset=0, write=request(11), ready=0)
    assert event['role'] == 'full_overwrite' and event['slot'] == expected
    assert reference.slots[expected]['payload'] == request(11)


def test_reset_removes_all_pending_and_shadow_entries():
    reference = filled()
    reference.advance(reset=1, write=request(5), ready=1)
    assert reference.slots == [dict(shadow_valid=0, dirty=0, payload=zero()) for _ in range(4)]
    assert reference.plru == 0


def test_reference_rejects_incomplete_payload():
    with pytest.raises(ValueError, match='full bounded'):
        WriteBufferReference().advance(reset=0, write={'set_index': 1}, ready=0)


def test_reference_rejects_duplicate_shadow_keys():
    reference = filled()
    reference.slots[1] = deepcopy(reference.slots[0])
    with pytest.raises(ValueError, match='duplicate shadow'):
        reference.advance(reset=0, write=request(5), ready=0)


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('s', range(64))
def test_public_feedback_to_full_payload_two_stage_and_real_drain(bank, s):
    reference = CapacityReference()
    tx = dict(pc=0x40000800 + 2 * s, target=0x40090000 + s * 0x100,
        taken=1, position=1, branch_type=1, ras_action=0, mispredict=1,
        meta=dict(valid=1, bankMask=1 << bank, setIdx=s,
                  entries=[dict(hit=0, position=0, attribute=dict(branchType=0, rasAction=0)) for _ in range(4)]))
    assert reference.advance(reset=0, accepted=tx, ready=[0] * 4) == ([], [])
    assert reference.request2 == [None] * 4
    assert reference.advance(reset=0, accepted=None, ready=[0] * 4) == ([], [])
    assert reference.request2[bank] == request(s)
    drains, actions = reference.advance(reset=0, accepted=None, ready=[0] * 4)
    assert not drains and len(actions) == 1 and actions[0]['slot'] == 0
    ready = [int(i == bank) for i in range(4)]
    drains, actions = reference.advance(reset=0, accepted=None, ready=ready)
    assert drains == [dict(bank=bank, slot=0, payload=request(s))] and not actions
    assert reference.sram[bank][s][0] == request(s)
    assert reference.counter.cells[bank * 256 + s * 4] == 2
