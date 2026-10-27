"""Hand-derived reference checks, without a DUT or observed expected values."""
from copy import deepcopy
from dataclasses import replace
import pytest
from bpuverify.mbtb.transaction.types import MbtbEntry
from bpuverify.mbtb.model.depth import expected_mbtb_depth_one_states

def prepared(align, owner, empty_counter):
    entries = tuple(MbtbEntry(0, 0, 0x40000000, (way // 5) * 16, 0, 0) for way in range(10))
    active = align * 5 + owner
    entries = tuple(replace(value, valid=1, taken=1, target=0x40009340, position=1 + align * 16, branch_type=3)
                    if way == active else value for way, value in enumerate(entries))
    metadata = [[dict(rawHit=0, position=bank * 16, counter_value=0,
                      attribute=dict(branchType=0, rasAction=0)) for _ in range(5)] for bank in range(2)]
    metadata[align][owner].update(rawHit=1, position=1 + align * 16, counter_value=2,
                                 attribute=dict(branchType=3, rasAction=0))
    metadata[align][1 - owner]['counter_value'] = empty_counter
    entries = tuple(replace(value, taken=int(empty_counter >= 2)) if way == align * 5 + 1 - owner else value
                    for way, value in enumerate(entries))
    first = dict(entries=deepcopy(entries), meta_entries=deepcopy(metadata))
    return [first, dict(entries=entries, meta_entries=metadata)]

@pytest.mark.parametrize('align', (0, 1))
@pytest.mark.parametrize('owner', (0, 1))
@pytest.mark.parametrize('empty_counter', (0, 2))
@pytest.mark.parametrize('ways', ((0, 1), (1, 0)))
def test_request_way_does_not_redefine_retained_entry_or_unmatched_payload(align, owner, empty_counter, ways):
    source = prepared(align, owner, empty_counter)
    before = deepcopy(source)
    result = expected_mbtb_depth_one_states(source, align, owner, (0x4000A340, 0x4010B340), ways)
    assert source == before and result[0] == before[0]
    assert result[1]['meta_entries'][align][owner]['counter_value'] == 2
    assert result[1]['meta_entries'][align][1 - owner] == before[1]['meta_entries'][align][1 - owner]
    assert result[1]['entries'][align * 5 + owner].target == 0x4010B340
    other = result[1]['entries'][align * 5 + 1 - owner]
    assert other == before[1]['entries'][align * 5 + 1 - owner]
    result[1]['meta_entries'][align][owner]['counter_value'] = 1
    assert source == before

@pytest.mark.parametrize('counter,hit', ((1, 0), (3, 0), (2, 1)))
def test_neighbor_presentation_does_not_need_a_weak_counter_or_empty_hit(counter, hit):
    source = prepared(0, 1, counter)
    source[1]['meta_entries'][0][0]['rawHit'] = hit
    if hit:
        source[1]['entries'] = (replace(source[1]['entries'][0], valid=1, branch_type=1, position=2),
                                *source[1]['entries'][1:])
        source[1]['meta_entries'][0][0].update(position=2, attribute=dict(branchType=1, rasAction=0))
    before = deepcopy(source)
    result = expected_mbtb_depth_one_states(source, 0, 1, (10, 20), (0, 1))
    assert result[1]['entries'][0] == source[1]['entries'][0]
    assert result[1]['meta_entries'][0][0] == source[1]['meta_entries'][0][0]
    assert source == before

@pytest.mark.parametrize('ways', ((0, 0), (1, 1), (), (0, 1, 0)))
def test_repeated_or_missing_request_way_is_rejected(ways):
    with pytest.raises(ValueError, match='exactly once'):
        expected_mbtb_depth_one_states(prepared(0, 1, 0), 0, 1, (10, 20), ways)
