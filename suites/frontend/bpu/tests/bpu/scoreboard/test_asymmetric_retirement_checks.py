"""Wrong pairing, stale data and incomplete evidence must fail without DUT credit."""
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.model.tage.asymmetric_retirement import SERVICE_IDENTITIES
from tests.bpu.scoreboard.asymmetric_retirement_fixtures import armed, held, packet, released, completed


def test_complete_services_compare_by_logical_identity_not_simultaneous_lane_pair():
    checks, _, retired = completed()
    assert SERVICE_IDENTITIES == (('neighbor-a', 'target-b'), ('target-a', 'neighbor-b'))
    assert checks.coverage.groups['checked'].coverage == 0 and not retired
    checks.finish()
    assert all(g.coverage == 100 for g in checks.coverage.groups.values())
    assert len(retired) == len(set(retired))
    with pytest.raises(AssertionError, match='single-use'):
        checks.finish()


@pytest.mark.parametrize('fault', ('paired-by-ordinal', 'old-requested-owner', 'stale-target-b', 'wrong-tag', 'duplicate', 'before-release'))
def test_wrong_complete_sdk_result_fails_with_logical_identity_and_current_state(fault):
    checks, _, _ = released()
    owner, index, tick = 0, 0, 40310
    if fault == 'stale-target-b':
        checks.write_accepted(0, NS(accepted_tick=tick, value=deepcopy(checks.expected_plan[0][0])))
        index, tick = 1, tick + 2
    value = deepcopy(checks.expected_plan[owner][index])
    if fault == 'paired-by-ordinal': value = deepcopy(checks.expected_plan[1][0])
    elif fault == 'old-requested-owner': owner = 1
    elif fault == 'stale-target-b': value['counter'] = 6
    elif fault == 'wrong-tag': value['tag'] ^= 1
    elif fault == 'before-release': tick = checks.release_tick
    else:
        for i in range(2):
            checks.write_accepted(0, NS(accepted_tick=40310 + 2 * i, value=deepcopy(checks.expected_plan[0][i])))
        tick = 40314
    with pytest.raises(AssertionError) as first:
        checks.write_accepted(owner, NS(accepted_tick=tick, value=value))
    with pytest.raises(AssertionError) as second:
        checks.finish()
    assert first.value is second.value and checks.coverage.groups['checked'].coverage == 0
    assert 'phase' in str(first.value)


@pytest.mark.parametrize('fault', ('wrong-hit-owner', 'same-retained-rank', 'pending-neighbor-lost', 'reread', 'missing-port', 'proposal-gap'))
def test_actual_late_feedback_must_reach_two_distinct_current_destinations(fault):
    checks, _, _ = held()
    checks.offered = checks.offered[:3]
    row = packet(checks, index=3)
    tick = 40108
    if fault == 'wrong-hit-owner': row['owner_hits'][0].update(owner0=(1, 0, 0), owner1=0)
    elif fault == 'same-retained-rank': row['hit_ranks'] = ((0, 0), (0, 0))
    elif fault == 'pending-neighbor-lost': row['state']['dirty'] = ((1, 0, 0, 0), (1, 1, 0, 0))
    elif fault == 'reread': row['state']['reads'][1]['valid'] = 1
    elif fault == 'missing-port': row['state']['incoming'][1]['valid'] = 0
    else:
        checks.capture_state(NS(tick=tick), row)
        row, tick = packet(checks, index=4), tick + 4
    before = deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=tick), row)
    with pytest.raises(AssertionError):
        checks.raise_failure()
    assert checks.pipeline.model.sources.tage.state() == before
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('phase,name', (('blocked', 'original'), ('blocked', 'neighbor'),
                                      ('serviced', 'original'), ('serviced', 'neighbor'), ('serviced', 'displaced')))
def test_each_complete_history_consumer_is_required(phase, name):
    checks, _, _ = completed()
    del checks.consumers[phase, name]
    with pytest.raises(AssertionError, match='six'):
        checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


def test_late_learning_and_each_actual_service_are_mandatory_before_final_credit():
    checks, _, _ = held(prelude_only=True)
    with pytest.raises(AssertionError, match='late learning'):
        checks.release()
    checks, _, _ = released()
    for owner in range(2):
        checks.write_accepted(owner, NS(accepted_tick=40310, value=deepcopy(checks.expected_plan[owner][0])))
    with pytest.raises(AssertionError, match='four'):
        checks.services_complete()


def test_changed_original_metadata_cannot_be_replaced_with_a_current_source():
    checks, _, _ = completed()
    checks.requests[0].meta.resolve['sequence'] ^= 1
    with pytest.raises(AssertionError, match='immutable'):
        checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


def test_one_port_preparation_does_not_turn_the_omitted_branch_into_not_taken():
    checks, _, _ = armed()
    checks.begin_read_window()
    checks.capture_state(NS(tick=40000), packet(checks, training=True))
    row = packet(checks, index=0)
    row['state']['incoming'][1].update(valid=1, bits=dict(checks.identities['target-b'], counter=4))
    checks.capture_state(NS(tick=40008), row)
    with pytest.raises(AssertionError, match='proposal'):
        checks.raise_failure()
