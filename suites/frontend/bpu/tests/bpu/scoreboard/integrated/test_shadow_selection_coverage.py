"""Independent golden payload, full replay faults and honest selection bins."""
from copy import deepcopy

import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.bpu.model.bypass.model import BypassReference
from suites.frontend.bpu.bpu.coverage.bypass.selection import ResponseSelectionCoverage
from suites.frontend.bpu.bpu.coverage.bypass.selection import response_selection_coverage_model
from tests.bpu.scoreboard.integrated.test_coverage_collection import inputs


def selection_trace():
    references = [BypassReference(0), BypassReference(1)]
    frames = []
    steps = [(1, inputs())]
    for index in range(9):
        steps += [(0, inputs(read_index=31, train_index=index)),
                  (0, inputs(read_index=31, train_index=index, allocate=1, allocate_taken=1,
                             allocate_position=index % 16, tag=100 + index))]
        if index == 2:
            steps.append((0, inputs(read_index=2)))  # Prefix mask7: priority slot2.
    steps.append((0, inputs(read_index=2)))  # Wrapped prefix mask1: fallback slot2.
    for reset, boundary in steps:
        def frame(phase):
            return dict(phase=phase, tick=len(frames) + 1, value=dict(reset=reset,
                tables=[dict(inputs=deepcopy(boundary), state=ref.state(), outputs=ref.outputs(boundary))
                        for ref in references]))
        frames.append(frame('preedge'))
        for reference in references:
            reference.advance(boundary, reset=bool(reset))
        frames.append(frame('rising'))
    # Hand-derived allocation #3 lives in slot2; allocation #9 overwrites only
    # slot0 and resets the mask to1, leaving the same payload outside priority.
    expected = dict(hit=1, data_valid=1, tag=102, position=2, counter=4)
    assert all(table['outputs']['response'] == expected for table in frames[-1]['value']['tables'])
    assert all(table['state']['chosen'] == 0 and table['state']['hits'][2] == 1
               for table in frames[-1]['value']['tables'])
    return dict(passed=True, bypass_records=frames)


def test_both_tables_check_full_fallback_payload_from_reset_and_keep_partial_denominator():
    coverage = ResponseSelectionCoverage()
    summary = coverage.collect(selection_trace(), required=((0, 2, 'fallback'), (1, 2, 'fallback')))
    assert summary['occurrences']['table1.slot2.fallback'] == 1
    assert summary['occurrences']['table1.slot2.priority'] >= 1
    assert summary['bins_required'] == 30 and summary['nominal_bins'] == 32
    assert not summary['complete_selection_matrix_proven']
    assert not summary['observed_state_used_to_seed_reference']
    witness = next(row for row in summary['witnesses'] if row['table'] == 1 and row['selection'] == 'fallback')
    assert witness['expected'] == witness['actual'] == dict(hit=1, data_valid=1, tag=102, position=2, counter=4)
    assert coverage.coverage.cross_coverage('all_dimensions') < 100


@pytest.mark.parametrize('fault', ('hit', 'data_valid', 'tag', 'position', 'counter',
                                  'chosen', 'neighbor', 'gap', 'phase', 'reset'))
def test_any_late_state_or_payload_fault_prevents_all_selection_credit(fault):
    trace = selection_trace()
    frame = trace['bypass_records'][-1]
    table = frame['value']['tables'][1]
    if fault in ('hit', 'data_valid', 'tag', 'position', 'counter'):
        table['outputs']['response'][fault] ^= 1
    elif fault == 'chosen': table['state']['chosen'] = 4
    elif fault == 'neighbor': table['state']['useful'][511] ^= 1
    elif fault == 'gap': frame['tick'] += 2
    elif fault == 'phase': frame['phase'] = 'preedge'
    else: trace['bypass_records'][0]['value']['reset'] = 0
    coverage = ResponseSelectionCoverage()
    with pytest.raises(ScoreboardMismatch):
        coverage.collect(trace, required=((1, 2, 'fallback'),))
    assert coverage.coverage.samples == 0


def test_required_fallback_cannot_be_replaced_by_a_priority_hit_of_the_same_payload():
    trace = selection_trace()
    trace['bypass_records'] = trace['bypass_records'][:-2]
    coverage = ResponseSelectionCoverage()
    with pytest.raises(ScoreboardMismatch, match='required_shadow_response_selection'):
        coverage.collect(trace, required=((1, 2, 'fallback'),))
    assert coverage.coverage.samples == 0


def test_preparation_fallback_does_not_satisfy_a_later_return_window():
    trace = selection_trace()
    tick = trace['bypass_records'][-1]['tick']
    coverage = ResponseSelectionCoverage()
    with pytest.raises(ScoreboardMismatch, match='required_shadow_response_selection'):
        coverage.collect(trace, required=((1, 2, 'fallback'),), required_after_tick=tick)
    assert coverage.coverage.samples == 0
    result = coverage.collect(trace, required=((1, 2, 'fallback'),), required_after_tick=tick - 1)
    assert result['required_witnesses'][0]['tick'] == tick
    assert result['required_witnesses'][0]['expected'] == dict(hit=1, data_valid=1, tag=102, position=2, counter=4)


@pytest.mark.parametrize('tick', (True, -1, 2.5, '3'))
def test_invalid_required_window_is_rejected(tick):
    with pytest.raises(ValueError):
        ResponseSelectionCoverage().collect(selection_trace(), required_after_tick=tick)


@pytest.mark.parametrize('table,slot,selection', ((True, 2, 'fallback'), (1, True, 'fallback'),
    (2, 2, 'fallback'), (1, 8, 'fallback'), (1, 0, 'fallback'), (1, 2, 'ready_valid')))
def test_unsupported_scope_cannot_create_bins(table, slot, selection):
    with pytest.raises(ValueError):
        ResponseSelectionCoverage().collect(selection_trace(), required=((table, slot, selection),))


def test_slot0_fallback_exclusion_is_a_mask_invariant_not_a_coverage_threshold():
    # Reset has no valid cells/hits. Every write produces a nonempty low-bit
    # prefix mask; idle cycles preserve it. For arbitrary hit sets, bit0 hits
    # are therefore priority hits, and a fallback can only choose slots1..7.
    for last_written_slot in range(8):
        mask = (1 << (last_written_slot + 1)) - 1
        for hits in range(256):
            preferred = hits & mask
            if hits and not preferred:
                assert hits.bit_length() - 1 in range(1, 8)
            if hits & 1:
                assert preferred & 1
    bins = response_selection_coverage_model().report()['crosses'][0]['bins']
    assert sum(row['kind'] == 'normal' for row in bins) == 30
    assert {tuple(row['tuple']) for row in bins if row['kind'] == 'ignore'} == {
        ('0', '0', 'fallback'), ('1', '0', 'fallback')}
