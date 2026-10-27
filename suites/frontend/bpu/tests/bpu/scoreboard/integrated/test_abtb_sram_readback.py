from copy import deepcopy
import pytest
from bpuverify.bpu.case.abtb.readback import matching_sram_readbacks

ENTRY = dict(valid=1, tag=123, position=7, branch_type=1, ras_action=0, target_low=456)


def trace():
    rows = []
    for tick in range(1, 5):
        banks = [dict(read_input=dict(valid=0, set_index=0),
                      sram=dict(read=[dict(ENTRY, valid=0) for _ in range(4)])) for _ in range(4)]
        rows.append(dict(tick=tick, phase='preedge' if tick % 2 else 'rising',
                         value=dict(reset=0, banks=banks)))
    rows[0]['value']['banks'][0]['read_input'] = dict(valid=1, set_index=5)
    rows[1]['value']['banks'][0]['sram']['read'][2] = deepcopy(ENTRY)
    # Same-sample request pins are already unrelated to the registered output.
    rows[1]['value']['banks'][0]['read_input'] = dict(valid=1, set_index=6)
    return rows


def run(rows, **kwargs):
    values = dict(bank=0, entry_set=5, expected_entry=ENTRY, begin_tick=0, end_tick=4)
    values.update(kwargs)
    return matching_sram_readbacks(rows, **values)


def test_registered_output_belongs_to_originating_request_not_current_pins():
    rows = trace()
    result = run(rows)
    assert result == [dict(tick=2, request_tick=1, response_tick=2, bank=0, set_index=5,
                           way=2, entry=ENTRY)]
    result[0]['entry']['tag'] = 0
    assert rows[1]['value']['banks'][0]['sram']['read'][2]['tag'] == 123


def test_same_sample_matching_cannot_create_a_read_transaction():
    rows = trace()
    rows[0]['value']['banks'][0]['sram']['read'][2] = deepcopy(ENTRY)
    rows[1]['value']['banks'][0]['sram']['read'][2]['valid'] = 0
    assert not run(rows)


def test_held_output_cannot_be_borrowed_by_later_invalid_request():
    rows = trace()
    rows[3]['value']['banks'][0]['sram']['read'][2] = deepcopy(ENTRY)
    assert len(run(rows)) == 1
    assert not run(rows, begin_tick=2)


@pytest.mark.parametrize('begin,end,count', [(0, 2, 1), (1, 2, 0), (0, 1, 0),
                                           (0, 3, 1), (2, 4, 0)])
def test_both_request_and_response_must_be_inside_exact_alias_window(begin, end, count):
    assert len(run(trace(), begin_tick=begin, end_tick=end)) == count


@pytest.mark.parametrize('side', [0, 1])
def test_reset_on_either_side_prevents_a_read_witness(side):
    rows = trace()
    rows[side]['value']['reset'] = 1
    assert not run(rows)


@pytest.mark.parametrize('field', ['valid', 'tag', 'position', 'branch_type', 'ras_action', 'target_low'])
def test_each_complete_payload_field_is_required(field):
    rows = trace()
    rows[1]['value']['banks'][0]['sram']['read'][2][field] ^= 1
    assert not run(rows)


@pytest.mark.parametrize('field,value', [('valid', 0), ('set_index', 6)])
def test_originating_request_valid_and_set_are_required(field, value):
    rows = trace()
    rows[0]['value']['banks'][0]['read_input'][field] = value
    assert not run(rows)


def test_other_bank_payload_does_not_count():
    assert not run(trace(), bank=1)


def test_multiple_way_witnesses_keep_their_identity():
    rows = trace()
    rows[1]['value']['banks'][0]['sram']['read'][3] = deepcopy(ENTRY)
    assert [row['way'] for row in run(rows)] == [2, 3]


@pytest.mark.parametrize('fault', ['gap', 'duplicate', 'same_phase', 'unknown_phase',
                                 'missing_initial_epoch', 'unknown_tick_type', 'truncated'])
def test_incomplete_or_ambiguous_monitor_stream_is_rejected(fault):
    rows = trace()
    if fault == 'gap':
        rows[1]['tick'] += 2
    elif fault == 'duplicate':
        rows[1]['tick'] = 1
    elif fault == 'same_phase':
        rows[1]['phase'] = 'preedge'
    elif fault == 'unknown_phase':
        rows[1]['phase'] = 'unknown'
    elif fault == 'missing_initial_epoch':
        rows = rows[1:]
    elif fault == 'unknown_tick_type':
        rows[1]['tick'] = 2.0
    else:
        rows.pop()
    with pytest.raises(ValueError):
        run(rows)


@pytest.mark.parametrize('kwargs', [dict(bank=True), dict(bank=4), dict(entry_set=True),
    dict(entry_set=-1), dict(entry_set=64), dict(begin_tick=True), dict(begin_tick=-1),
    dict(begin_tick=4), dict(end_tick=5), dict(end_tick=0)])
def test_invalid_physical_or_window_identity_is_not_relabelled(kwargs):
    with pytest.raises(ValueError):
        run(trace(), **kwargs)


def test_empty_observation_is_not_a_successful_association():
    with pytest.raises(ValueError):
        run([])
