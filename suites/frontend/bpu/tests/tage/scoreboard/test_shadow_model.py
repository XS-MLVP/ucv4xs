"""Hand-derived retained-owner transitions, independent of native RTL."""
from copy import deepcopy

import pytest

from bpuverify.tage.model.shadow import advance_tage_shadow
from bpuverify.tage.model.shadow import expected_tage_cross_owner_writes


def empty_banks():
    return [[[dict(valid=0, dirty=0, set_idx=0, tag=0, entry_valid=0, counter=0)
              for _ in range(4)] for _ in range(2)] for _ in range(4)]


def request(**changes):
    return dict(set_idx=37, tag=341, entry_valid=1, counter=1, taken=1, **changes)


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('port', range(2))
@pytest.mark.parametrize('depth', range(4))
@pytest.mark.parametrize('dirty', (0, 1))
def test_counter_uses_retained_owner_and_depth_not_requesting_port(bank, port, depth, dirty):
    before = empty_banks()
    before[bank][1-port][depth] = dict(valid=1, dirty=dirty, set_idx=37, tag=341, entry_valid=1, counter=6)
    frozen = deepcopy(before)
    expected = deepcopy(before)
    expected[bank][1-port][depth].update(dirty=1, counter=7)
    after = advance_tage_shadow(before, [[1-dirty]*2 for _ in range(4)],
                               bank=bank, port=port, write=request())
    assert after == dict(banks=expected, owner=1-port, depth=depth)
    assert before == frozen
    after['banks'][bank][1-port][depth]['tag'] = 0
    assert before == frozen


@pytest.mark.parametrize('counter,taken,requested', ((7, 1, 6), (0, 0, 1), (1, 0, 6), (6, 1, 2)))
def test_counter_saturates_or_steps_from_shadow_not_stale_payload(counter, taken, requested):
    before = empty_banks()
    before[2][1][3] = dict(valid=1, dirty=1, set_idx=37, tag=341, entry_valid=1, counter=counter)
    write = dict(set_idx=37, tag=341, entry_valid=1, counter=requested, taken=taken)
    result = advance_tage_shadow(before, [[0, 0]]*4, bank=2, port=0, write=write)
    assert result['banks'][2][1][3]['counter'] == (7 if taken else 0)
    assert result['banks'][2][1][3]['dirty'] == 1
    assert result['banks'][2][0] == before[2][0]


def test_drain_clears_priority_slot_in_every_owner_then_same_slot_write_wins():
    before = empty_banks()
    for bank in range(4):
        for owner in range(2):
            for depth in (1, 3):
                before[bank][owner][depth] = dict(valid=1, dirty=1, set_idx=depth,
                    tag=20+owner, entry_valid=1, counter=5)
    write = dict(set_idx=1, tag=21, entry_valid=1, counter=2, taken=0)
    expected = deepcopy(before)
    for bank in expected:
        for row in bank:
            row[1]['dirty'] = 0
    expected[2][1][1].update(dirty=1, counter=4)
    result = advance_tage_shadow(before, [[1, 1]]*4, bank=2, port=0, write=write)
    assert result == dict(banks=expected, owner=1, depth=1)


def test_new_key_uses_first_clean_slot_without_counter_forwarding():
    before = empty_banks()
    before[1][0][0] = dict(valid=1, dirty=1, set_idx=0, tag=0, entry_valid=1, counter=7)
    before[1][0][1] = dict(valid=1, dirty=0, set_idx=8, tag=0, entry_valid=1, counter=7)
    result = advance_tage_shadow(before, [[0, 0]]*4, bank=1, port=0, write=request())
    assert (result['owner'], result['depth']) == (0, 1)
    assert result['banks'][1][0][1] == dict(valid=1, dirty=1, set_idx=37, tag=341, entry_valid=1, counter=1)


def test_same_set_victim_has_priority_over_earlier_clean_slot():
    before = empty_banks()
    before[1][0][3] = dict(valid=1, dirty=1, set_idx=37, tag=340, entry_valid=1, counter=7)
    result = advance_tage_shadow(before, [[0, 0]]*4, bank=1, port=0, write=request())
    assert result['depth'] == 3 and result['banks'][1][0][3]['counter'] == 1
    assert result['banks'][1][0][0] == before[1][0][0]


def test_no_write_drains_but_retains_keys_and_counter():
    before = empty_banks()
    before[0][1][2] = dict(valid=1, dirty=1, set_idx=37, tag=341, entry_valid=1, counter=6)
    expected = deepcopy(before)
    expected[0][1][2]['dirty'] = 0
    assert advance_tage_shadow(before, [[1, 1]]*4) == dict(banks=expected, owner=None, depth=None)


def test_full_miss_does_not_invent_plru_or_reuse_same_cycle_drain():
    before = empty_banks()
    for depth in range(4):
        before[0][0][depth] = dict(valid=1, dirty=1, set_idx=depth, tag=1, entry_valid=1, counter=5)
    with pytest.raises(ValueError, match='full-row miss/PLRU'):
        advance_tage_shadow(before, [[1, 1]]*4, bank=0, port=0, write=request())


def test_duplicate_retained_key_is_rejected():
    before = empty_banks()
    for owner in range(2):
        before[0][owner][0] = dict(valid=1, dirty=0, set_idx=37, tag=341, entry_valid=1, counter=5)
    with pytest.raises(ValueError, match='ambiguous.*key'):
        advance_tage_shadow(before, [[0, 0]]*4, bank=0, port=0, write=request())


@pytest.mark.parametrize('bank,port,write', ((4, 0, request()), (0, 2, request()), (0, None, request()),
    (0, 0, dict(set_idx=37, tag=341, entry_valid=1, counter=8, taken=1)), (0, 0, None)))
def test_invalid_request_is_rejected_before_transition(bank, port, write):
    with pytest.raises(ValueError):
        advance_tage_shadow(empty_banks(), [[0, 0]]*4, bank=bank, port=port, write=write)


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('origin', range(2))
def test_cross_owner_requests_keep_stale_payload_separate_from_forwarded_counter(bank, origin):
    pc = 0x40000000+bank
    frames = expected_tage_cross_owner_writes(pc, 6, origin,
        ((pc+0x20, 4), (pc+0x40, 5), (pc+0x60, 7)))
    assert len(frames) == 7
    for index, frame in enumerate(frames):
        port = 1-origin if index < 4 else origin
        position = (4, 5, 7, 6, 6, 6, 6)[index]
        set_idx = (8, 16, 24, 0, 0, 0, 0)[index]
        counter = (7, 7, 7, 5, 6, 6, 6)[index]
        assert frame[bank][port] == dict(set_idx=set_idx, tag=position, counter=counter, entry_valid=1, taken=1)
        assert frame[bank][1-port] is None
        assert all(row == (None, None) for other, row in enumerate(frame) if other != bank)
    frames[-1][bank][origin]['counter'] = 0
    assert frames[-2][bank][origin]['counter'] == 6


@pytest.mark.parametrize('pc,target,origin,prefix', ((-1, 6, 0, ()), (0, 9, 0, ()), (0, 6, 2, ()),
    (0, 6, 0, ((1, 4),)), (0, 6, 0, ((0, 4),)), (0, 6, 0, ((4, 4),)*4)))
def test_cross_owner_payload_model_rejects_unsupported_scope(pc, target, origin, prefix):
    with pytest.raises(ValueError):
        expected_tage_cross_owner_writes(pc, target, origin, prefix)
