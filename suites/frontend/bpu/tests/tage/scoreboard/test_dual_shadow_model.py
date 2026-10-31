"""Hand-derived simultaneous writes; no RTL observation supplies expectations."""
from copy import deepcopy

import pytest

from suites.frontend.bpu.tage.model.dual_shadow import advance_tage_shadow_writes
from suites.frontend.bpu.tage.model.shadow import advance_tage_shadow


def resident_banks():
    return [[[dict(valid=1, dirty=1, set_idx=depth + 8 * owner,
                   tag=100 + bank * 16 + owner * 4 + depth,
                   entry_valid=1, counter=7)
              for depth in range(4)] for owner in range(2)] for bank in range(4)]


def payload(port):
    return dict(set_idx=37, tag=341 + port, entry_valid=1,
                counter=(1, 6)[port], taken=port)


def frame(bank, *writes):
    result = [[None, None] for _ in range(4)]
    result[bank] = list(writes)
    return result


def drain(before, ready):
    expected = deepcopy(before)
    for bank in range(4):
        for owner in range(2):
            for depth, slot in enumerate(before[bank][owner]):
                if slot['dirty'] and ready[bank][owner]:
                    expected[bank][owner][depth]['dirty'] = 0
                    break
    return expected


def witness(before, ready, bank, port, owner, depth, write, new_counter, hit):
    slot = before[bank][owner][depth]
    return dict(bank=bank, request_port=port, owner=owner, depth=depth, hit=hit,
                old_counter=slot['counter'], request_counter=write['counter'],
                new_counter=new_counter, dirty=slot['dirty'], ready=ready[bank][owner],
                old_valid=slot['valid'], old_set_idx=slot['set_idx'], old_tag=slot['tag'])


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('depth', range(4))
@pytest.mark.parametrize('cross_owner', (False, True))
@pytest.mark.parametrize('dirty,ready_bit', ((0, 0), (0, 1), (1, 0), (1, 1)))
@pytest.mark.parametrize('counters', ((0, 7), (1, 6), (2, 5)))
def test_two_hits_use_one_prestate_and_keep_both_independent_updates(
        bank, depth, cross_owner, dirty, ready_bit, counters):
    before = resident_banks()
    writes = [payload(0), payload(1)]
    # Deliberately unrelated stale request counters, including both saturation ends.
    writes[0]['counter'], writes[1]['counter'] = 6, 1
    owners = (1, 0) if cross_owner else (0, 1)
    ready = [[1, 0] for _ in range(4)]
    ready[bank] = [ready_bit, ready_bit]
    for port, owner in enumerate(owners):
        before[bank][owner][depth].update(set_idx=37, tag=341 + port,
                                          counter=counters[port], dirty=dirty)
    frozen, requests = deepcopy(before), frame(bank, *writes)
    frozen_requests = deepcopy(requests)
    expected, expected_writes = drain(before, ready), []
    for port, owner in enumerate(owners):
        counter = max(0, counters[0] - 1) if port == 0 else min(7, counters[1] + 1)
        expected[bank][owner][depth].update(counter=counter, dirty=1)
        expected_writes.append(witness(before, ready, bank, port, owner, depth,
                                       writes[port], counter, 1))
    actual = advance_tage_shadow_writes(before, ready, requests)
    assert actual == dict(banks=expected, writes=tuple(expected_writes))
    assert before == frozen and requests == frozen_requests
    actual['banks'][bank][owners[0]][depth]['tag'] = 0
    assert before == frozen and requests == frozen_requests


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('depth', range(4))
@pytest.mark.parametrize('ready_bit', (0, 1))
def test_two_misses_select_precycle_clean_slots_and_copy_request_counters(bank, depth, ready_bit):
    before = resident_banks()
    for row in before[bank]:
        row[depth]['dirty'] = 0
    ready = [[0, 0] for _ in range(4)]
    ready[bank] = [ready_bit, ready_bit]
    expected, records = drain(before, ready), []
    requests = frame(bank, payload(0), payload(1))
    frozen, frozen_requests = deepcopy(before), deepcopy(requests)
    for port, write in enumerate(requests[bank]):
        expected[bank][port][depth].update(valid=1, dirty=1, set_idx=37,
            tag=341 + port, entry_valid=1, counter=write['counter'])
        records.append(witness(before, ready, bank, port, port, depth,
                               write, write['counter'], 0))
    assert advance_tage_shadow_writes(before, ready, requests) == dict(
        banks=expected, writes=tuple(records))
    assert before == frozen and requests == frozen_requests


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('depth', range(4))
@pytest.mark.parametrize('mode', ('companion_dirty_hit', 'companion_clean_hit', 'companion_miss'))
def test_mixed_hit_miss_keeps_old_counter_and_new_key_initialization_distinct(bank, depth, mode):
    before = resident_banks()
    ready = [[0, 0] for _ in range(4)]
    for row in before[bank]:
        row[depth]['dirty'] = 0
    requests = frame(bank, payload(0), payload(1))
    if mode == 'companion_miss':
        before[bank][0][depth].update(set_idx=37, tag=341, counter=0, dirty=1)
        selected_depths, hits, counters = (depth, depth), (1, 0), (0, 6)
    else:
        companion_depth = 0 if mode == 'companion_clean_hit' else depth
        before[bank][1][companion_depth].update(set_idx=37, tag=342, counter=6,
            dirty=int(mode == 'companion_dirty_hit'))
        selected_depths, hits, counters = (depth, companion_depth), (0, 1), (1, 7)
    expected, records, frozen = drain(before, ready), [], deepcopy(before)
    for port, write in enumerate(requests[bank]):
        selected = selected_depths[port]
        expected[bank][port][selected].update(valid=1, dirty=1, set_idx=37,
            tag=341 + port, entry_valid=1, counter=counters[port])
        records.append(witness(before, ready, bank, port, port, selected,
                               write, counters[port], hits[port]))
    assert advance_tage_shadow_writes(before, ready, requests) == dict(
        banks=expected, writes=tuple(records))
    assert before == frozen


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('port', range(2))
def test_zero_and_one_write_remain_equivalent_to_single_write_reference(bank, port):
    before = resident_banks()
    before[bank][port][2].update(set_idx=37, tag=341 + port)
    ready = [[1, 1] for _ in range(4)]
    inactive = [[None, None] for _ in range(4)]
    assert advance_tage_shadow_writes(before, ready, inactive) == dict(
        banks=advance_tage_shadow(before, ready)['banks'], writes=())
    inactive[bank][port] = payload(port)
    expected = advance_tage_shadow(before, ready, bank=bank, port=port, write=payload(port))
    actual = advance_tage_shadow_writes(before, ready, inactive)
    assert actual['banks'] == expected['banks']
    assert len(actual['writes']) == 1
    assert actual['writes'][0]['request_port'] == port


@pytest.mark.parametrize('requests', (None, [], [[None, None]] * 3,
    [[None]] * 4, [[None, None, None]] * 4, [[None, None]] * 3 + [None]))
def test_invalid_frame_shape_is_rejected_without_mutation(requests):
    before = resident_banks()
    frozen = deepcopy(before)
    with pytest.raises(ValueError, match='four banks and two ports'):
        advance_tage_shadow_writes(before, [[0, 0]] * 4, requests)
    assert before == frozen


@pytest.mark.parametrize('field,value', (('counter', 8), ('counter', -1), ('taken', 2),
    ('set_idx', 512), ('tag', 8192), ('entry_valid', 2), ('counter', '1')))
def test_invalid_second_write_does_not_partially_apply_first(field, value):
    before = resident_banks()
    for row in before[0]:
        row[0]['dirty'] = 0
    requests = frame(0, payload(0), payload(1))
    requests[0][1][field] = value
    frozen, frozen_requests = deepcopy(before), deepcopy(requests)
    with pytest.raises(ValueError, match='invalid TAGE single-write request'):
        advance_tage_shadow_writes(before, [[1, 1]] * 4, requests)
    assert before == frozen and requests == frozen_requests


@pytest.mark.parametrize('kind', ('non_mapping', 'foreign_bank', 'three_ports',
    'different_sets', 'duplicate_key', 'slot_collision', 'full_miss', 'duplicate_retained_key'))
def test_unsupported_or_ambiguous_pair_is_explicitly_rejected(kind):
    before = resident_banks()
    for row in before[0]:
        row[0]['dirty'] = 0
    requests = frame(0, payload(0), payload(1))
    if kind == 'non_mapping':
        requests[0][1] = 1
    elif kind == 'foreign_bank':
        requests[1][1], requests[0][1] = requests[0][1], None
    elif kind == 'three_ports':
        requests[1][1] = payload(1)
    elif kind == 'different_sets':
        requests[0][1]['set_idx'] = 38
    elif kind == 'duplicate_key':
        requests[0][1]['tag'] = requests[0][0]['tag']
    elif kind == 'slot_collision':
        # Port 0 hits owner 1; port 1's different tag chooses that same-set slot.
        before[0][1][0].update(set_idx=37, tag=341)
    elif kind == 'full_miss':
        for row in before[0]:
            for slot in row:
                slot['dirty'] = 1
    else:
        for row in before[0]:
            row[0].update(set_idx=37, tag=341)
    frozen, frozen_requests = deepcopy(before), deepcopy(requests)
    with pytest.raises(ValueError):
        advance_tage_shadow_writes(before, [[1, 1]] * 4, requests)
    assert before == frozen and requests == frozen_requests
