"""Read-dependent request payloads and frozen forwarding state expectations."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from suites.frontend.bpu.tage.model.overlap import expected_tage_overlapped_states
from suites.frontend.bpu.tage.model.overlap import expected_tage_overlapped_writes
from suites.frontend.bpu.tage.agent.main import TageAgent


@pytest.mark.parametrize('pc', (0x40000000, 0x40000020, 0x40000001, 0x40000400))
@pytest.mark.parametrize('way', (0, 1))
def test_overlap_requests_keep_bank_set_way_and_two_cold_tags(pc, way):
    expected = expected_tage_overlapped_writes(pc, 6, way, 2, mode='adjacent')
    assert expected['beats'] == 2 and expected['latency_ticks'] == (8, 8)
    for frame, newcomer in zip(expected['banks'], (17, 18), strict=True):
        ports = frame[pc & 3]
        assert ports[way] == {'set_idx':(pc >> 2)&511, 'tag':((pc >> 11)&8191)^6,
                             'counter':1, 'entry_valid':1, 'taken':0}
        assert ports[1-way] == {'set_idx':(pc >> 2)&511, 'tag':((pc >> 11)&8191)^newcomer,
                               'counter':4, 'entry_valid':1, 'taken':1}
        assert all(bank == (None,None) for i,bank in enumerate(frame) if i != pc&3)


@pytest.mark.parametrize('counter', (1, 2))
@pytest.mark.parametrize('mode', ('adjacent', 'separated'))
def test_adjacent_old_read_and_separated_current_read_have_distinct_requests(counter, mode):
    first, second = expected_tage_overlapped_writes(0, 6, 0, counter, mode=mode)['banks']
    assert first[0][0]['counter'] == counter-1
    if mode == 'separated' and counter == 1:
        assert second[0][0] is None
    else:
        assert second[0][0]['counter'] == (counter-1 if mode == 'adjacent' else counter-2)
    assert second[0][1]['counter'] == 4 and second[0][1]['tag'] == 18


@pytest.mark.parametrize('pc,position,way,counter,mode', (
    (-1,6,0,1,'adjacent'), (0,17,0,1,'adjacent'), (0,6,2,1,'adjacent'),
    (0,6,0,0,'adjacent'), (0,6,0,3,'adjacent'), (0,6,0,1,'fresh'),
))
def test_overlap_reference_rejects_unsupported_scope(pc, position, way, counter, mode):
    with pytest.raises(ValueError):
        expected_tage_overlapped_writes(pc, position, way, counter, mode=mode)


def test_write_frames_do_not_share_mutable_port_payloads():
    expected = expected_tage_overlapped_writes(0, 6, 0, 2, mode='adjacent')
    expected['banks'][0][0][0]['counter'] = 7
    assert expected['banks'][1][0][0]['counter'] == 1


def prepared_states():
    return {6:{'valid':1,'meta':{'providerTakenCtr_value':2,'providerUsefulCtr_value':3,
                              'providerTableIdx':7,'providerWayIdx':0}},
                7:{'valid':1,'meta':{'providerTakenCtr_value':5,'providerUsefulCtr_value':0,
                                   'providerTableIdx':7,'providerWayIdx':1}},
                2:{'valid':1,'meta':{'providerTakenCtr_value':7,'providerUsefulCtr_value':3}}}


def test_final_reference_saturates_target_replaces_two_victims_and_is_frozen():
    prepared = prepared_states()
    original = deepcopy(prepared)
    states = expected_tage_overlapped_states(prepared,6,7,0)
    assert prepared == original and states[6]['meta']['providerTakenCtr_value'] == 0
    assert states[6]['meta']['providerUsefulCtr_value'] == 3
    assert states[7] is states[17] is None and states[2] == prepared[2]
    assert states[18]['meta']['providerWayIdx'] == 1 and states[18]['meta']['providerTakenCtr_value'] == 4
    prepared[2]['meta']['providerTakenCtr_value'] = 0
    assert states[2]['meta']['providerTakenCtr_value'] == 7


@pytest.mark.parametrize('field,value', (('providerTakenCtr_value',0), ('providerTakenCtr_value',3),
    ('providerTableIdx',2), ('providerWayIdx',1), ('providerUsefulCtr_value',2)))
def test_final_reference_rejects_unprepared_target_state(field, value):
    prepared = prepared_states()
    prepared[6]['meta'][field] = value
    with pytest.raises(ValueError):
        expected_tage_overlapped_states(prepared,6,7,0)


async def test_empty_checked_feedback_burst_is_rejected_before_drive_or_observation():
    with pytest.raises(ValueError, match='must not be empty'):
        await TageAgent.train_batches_with_writes_checked(SimpleNamespace(), (), [], [], expected_activity={})
