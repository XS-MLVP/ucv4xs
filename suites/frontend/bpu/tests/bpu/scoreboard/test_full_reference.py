"""Pure model contracts, explicitly not evidence of native reachability."""
from copy import deepcopy
from itertools import product
import pytest
from bpuverify.bpu.model.sc.model import NAMES
from bpuverify.bpu.model.sc.model import advance
from bpuverify.bpu.model.sc.model import zero_slots
from bpuverify.bpu.model.sc.model import width
from bpuverify.abtb.model.state.replacer import touch
from bpuverify.abtb.model.state.replacer import victim
from bpuverify.bpu.model.sc.full import FullScReference, full_advance
from tests.bpu.scoreboard.test_used_reference import transaction
from bpuverify.bpu.model.sc.used import used_requests

def payload(key, ways=4, value=1, lane=0):
    return dict(set_index=key, masks=[int(i == lane) for i in range(ways)], data=[value if i == lane else 0 for i in range(ways)])

def resident_slots(ways=4, dirty_mask=15):
    return [dict(valid=1, dirty=dirty_mask >> i & 1, payload=payload(i, ways, value=i + 1, lane=i)) for i in range(4)]

@pytest.mark.parametrize('ways', [4, 16])
@pytest.mark.parametrize('plru', range(8))
@pytest.mark.parametrize('ready', [0, 1])
def test_full_miss_every_plru_state_and_old_drain(ways, plru, ready):
    slots = resident_slots(ways)
    old, write = (deepcopy(slots), payload(4, ways, value=63, lane=ways - 1))
    new, next_plru, drain, action = full_advance(slots, plru=plru, ready=ready, write=write)
    selected = (0, 1, 0, 1, 2, 2, 3, 3)[plru]
    assert victim(plru) == selected
    assert action['slot'] == selected and action['kind'] == 'full_overwrite'
    assert new[selected] == dict(valid=1, dirty=1, payload=write)
    assert drain == (old[0]['payload'] if ready else None)
    for slot in range(4):
        if slot != selected:
            expected = deepcopy(old[slot])
            if ready and slot == 0:
                expected['dirty'] = 0
            assert new[slot] == expected
    assert action['overwritten_pending'] == (not (ready and selected == 0))
    assert action['drain_same_slot'] == bool(ready and selected == 0)
    assert action['before'] == old[selected] and action['full_before'] == 1
    assert next_plru == touch(plru, selected)
    assert slots == old

@pytest.mark.parametrize('ways', [4, 16])
@pytest.mark.parametrize('dirty_mask', range(16))
@pytest.mark.parametrize('ready', [0, 1])
@pytest.mark.parametrize('write_key', [None, 0, 1, 2, 3, 4])
def test_all_bounded_transitions_exactly_preserved(ways, dirty_mask, ready, write_key):
    slots = resident_slots(ways, dirty_mask)
    write = None if write_key is None else payload(write_key, ways, value=17, lane=ways - 1)
    if dirty_mask == 15 and write_key == 4:
        with pytest.raises(ValueError, match='full dirty overwrite'):
            advance(slots, ready=ready, write=write)
        return
    old_new, old_drain, old_kind = advance(slots, ready=ready, write=write)
    for plru in range(8):
        new, next_plru, drain, action = full_advance(slots, plru=plru, ready=ready, write=write)
        assert (new, drain, None if action is None else action['kind']) == (old_new, old_drain, old_kind)
        assert next_plru == (touch(plru, action['slot']) if write_key == 4 else plru)

@pytest.mark.parametrize('ways', [4, 16])
@pytest.mark.parametrize('slot', range(4))
@pytest.mark.parametrize('same', [0, 1])
def test_clean_same_does_not_reactivate_but_partial_mask_merge_retains_full_data(ways, slot, same):
    slots = resident_slots(ways, 15 ^ 1 << slot)
    write = deepcopy(slots[slot]['payload']) if same else payload(slot, ways, 63, ways - 1)
    new, plru, drain, action = full_advance(slots, plru=7, ready=0, write=write)
    assert plru == 7 and drain is None
    assert action['kind'] == ('clean_same' if same else 'clean_reactivate')
    assert new[slot]['dirty'] == (0 if same else 1)
    if not same:
        assert new[slot]['payload']['data'][slot] == (63 if slot == ways - 1 else slot + 1)
        assert new[slot]['payload']['data'][-1] == 63
        assert new[slot]['payload']['masks'][slot] == new[slot]['payload']['masks'][-1] == 1

@pytest.mark.parametrize('bank', [0, 1])
@pytest.mark.parametrize('way', range(4))
def test_five_real_input_derived_keys_full_overwrite_and_full_sram_drain(bank, way):
    ref = FullScReference()
    all_actions = []
    transactions = [transaction(bank=bank, way=way, key=key) for key in range(5)]
    for tx in transactions:
        drains, actions = ref.step(used_requests(tx, ref.memories), dict.fromkeys(NAMES, 0))
        assert not drains
        all_actions.extend(actions)
    active = [f'{table}_bank{bank}' for table in ('pathTable_0', 'globalTable_0', 'bwTable_0', 'imliTable', 'biasTable')]
    overwritten = [row for row in all_actions if row['kind'] == 'full_overwrite']
    assert {row['buffer'] for row in overwritten} == set(active)
    assert all((row['slot'] == 0 and row['overwritten_pending'] for row in overwritten))
    assert all((ref.memories[name] == {} for name in NAMES))
    expected = {name: {slot['payload']['set_index']: deepcopy(slot['payload']) for slot in ref.slots[name]} for name in active}
    drains = []
    for _ in range(4):
        more, actions = ref.step({}, dict.fromkeys(NAMES, 1))
        assert not actions
        drains.extend(more)
    assert len(drains) == 20
    for name in active:
        assert set(ref.memories[name]) == set(expected[name])
        for key, item in expected[name].items():
            assert ref.memories[name][key] == [value if mask else 0 for value, mask in zip(item['data'], item['masks'], strict=True)]
    assert all((not slot['dirty'] for slots in ref.slots.values() for slot in slots))
    ref.reset()
    assert all((state == 0 for state in ref.plru.values()))
    assert all((not rows for rows in ref.memories.values()))

@pytest.mark.parametrize('bank', [0, 1])
def test_same_cycle_old_drain_survives_replacement_and_new_write_remains_dirty(bank):
    ref = FullScReference()
    for key in range(4):
        ref.step(used_requests(transaction(bank=bank, key=key), ref.memories), dict.fromkeys(NAMES, 0))
    old = deepcopy(ref.slots)
    drains, actions = ref.step(used_requests(transaction(bank=bank, key=4), ref.memories), dict.fromkeys(NAMES, 1))
    assert len(drains) == len(actions) == 5
    assert all((row['drain_same_slot'] and (not row['overwritten_pending']) for row in actions))
    for row in drains:
        name, item = (row['buffer'], row['payload'])
        assert item == old[name][0]['payload']
        assert ref.slots[name][0]['dirty'] == 1
        assert ref.slots[name][0]['payload']['set_index'] != item['set_index']
        assert ref.memories[name][item['set_index']] == item['data']

@pytest.mark.parametrize('invalid', ['unknown_request', 'missing_ready', 'bad_ready', 'bad_payload', 'duplicate', 'dirty_invalid'])
def test_invalid_transition_does_not_partially_commit_any_table(invalid):
    ref = FullScReference()
    ready = dict.fromkeys(NAMES, 0)
    requests = {NAMES[-1]: payload(1, width(NAMES[-1]))}
    if invalid == 'unknown_request':
        requests['not_a_table'] = payload(1)
    if invalid == 'missing_ready':
        ready.pop(NAMES[-1])
    if invalid == 'bad_ready':
        ready[NAMES[-1]] = 2
    if invalid == 'bad_payload':
        requests[NAMES[-1]]['data'][0] = 64
    if invalid == 'duplicate':
        ref.slots[NAMES[-1]][0]['valid'] = ref.slots[NAMES[-1]][1]['valid'] = 1
    if invalid == 'dirty_invalid':
        ref.slots[NAMES[-1]][0]['dirty'] = 1
    old = deepcopy(vars(ref))
    with pytest.raises(ValueError):
        ref.step(requests, ready)
    assert vars(ref) == old
