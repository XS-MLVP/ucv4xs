"""Depth ownership requirements, before repair of the legacy helper."""
from copy import deepcopy
from dataclasses import replace

import pytest

from suites.frontend.bpu.mbtb.model.depth import expected_mbtb_depth_one_states
from tests.mbtb.scoreboard.test_depth_model import prepared


def with_peer(counter, *, filtered=False):
    profiles = prepared(0, 1, counter)
    peer = replace(profiles[1]['entries'][0], valid=int(not filtered), taken=int(counter >= 2),
                   target=0x4000B340, position=2, branch_type=1)
    profiles[1]['entries'] = (peer, *profiles[1]['entries'][1:])
    profiles[1]['meta_entries'][0][0].update(rawHit=1, position=2, counter_value=counter,
        attribute=dict(branchType=1, rasAction=0))
    return profiles


@pytest.mark.parametrize('counter', (0, 1, 3))
@pytest.mark.parametrize('filtered', (False, True))
def test_retained_target_rewrite_preserves_every_defined_nonweak_peer_field(counter, filtered):
    source = with_peer(counter, filtered=filtered)
    before = deepcopy(source)
    result = expected_mbtb_depth_one_states(source, 0, 1, (0x4000A340, 0x4010B340), (0, 1))
    assert source == before
    assert result[0] == before[0]
    assert result[1]['entries'][0] == before[1]['entries'][0]
    assert result[1]['meta_entries'][0][0] == before[1]['meta_entries'][0][0]
    assert result[1]['entries'][1].target == 0x4010B340
    assert result[1]['meta_entries'][0][1]['counter_value'] == 2


def test_an_unmatched_payload_is_not_invented_by_request_way_initialization():
    source = prepared(0, 1, 0)
    result = expected_mbtb_depth_one_states(source, 0, 1, (0x4000A340, 0x4010B340), (0, 1))
    assert result[1]['entries'][0] == source[1]['entries'][0]
    assert result[1]['meta_entries'][0][0] == source[1]['meta_entries'][0][0]
