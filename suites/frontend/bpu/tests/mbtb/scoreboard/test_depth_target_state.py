"""A logical rewrite has no request-way or two-offer prerequisite."""
from copy import deepcopy

import pytest

from suites.frontend.bpu.mbtb.model.depth import expected_depth_target_state
from tests.mbtb.scoreboard.test_depth_owner import with_peer


def test_single_logical_rewrite_preserves_complete_peer_and_first_key():
    source = with_peer(0)
    original = deepcopy(source)
    target = (1 << 49) - 1
    result = expected_depth_target_state(source, 0, 1, target)
    assert source == original and result[0] == original[0]
    assert result[1]['entries'][1].target == target
    assert result[1]['meta_entries'][0][1]['counter_value'] == 2
    assert result[1]['entries'][0] == original[1]['entries'][0]
    assert result[1]['meta_entries'][0][0] == original[1]['meta_entries'][0][0]
    result[0]['meta_entries'][0][1]['counter_value'] = 0
    result[1]['meta_entries'][0][0]['attribute']['branchType'] = 0
    assert source == original


@pytest.mark.parametrize('target', (-1, 1 << 49, True))
def test_logical_rewrite_rejects_out_of_domain_target(target):
    with pytest.raises(ValueError, match='49-bit halfword'):
        expected_depth_target_state(with_peer(0), 0, 1, target)


@pytest.mark.parametrize('field,value', (('rawHit', 0), ('counter_value', 1), ('position', 7)))
def test_logical_rewrite_requires_a_coherent_declared_indirect_owner(field, value):
    source = with_peer(0)
    source[1]['meta_entries'][0][1][field] = value
    with pytest.raises(ValueError, match='indirect'):
        expected_depth_target_state(source, 0, 1, 0x4000A340)
