"""Streaming retains reset, cadence, full-state and atomic-credit contracts."""
from copy import deepcopy
from heapq import merge

import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.bpu.coverage.abtb.session import CounterCaseCoverage
from suites.frontend.bpu.bpu.coverage.abtb.supplemental import CounterCoverage
from suites.frontend.bpu.bpu.coverage.bypass.supplemental import IntegratedCoverage
from tests.bpu.scoreboard.integrated.test_abtb_counter_coverage import full_path_trace
from tests.bpu.scoreboard.integrated.test_coverage_collection import useful_trace


def feed_counter(replay, trace):
    for tick, phase, row in merge(
            ((row['tick'], 'preedge', row) for row in trace['preedge_records']),
            ((row['tick'], 'rising', row) for row in trace['records'])):
        replay.observe(dict(row, phase=phase, tick=tick))


def test_stream_matches_offline_counter_summary_and_keeps_credit_uncommitted():
    trace = full_path_trace()
    offline = CounterCoverage().collect(trace)
    coverage = CounterCoverage()
    replay = coverage.stream()
    feed_counter(replay, trace)
    assert all(group.samples == 0 for group in coverage.groups)
    assert replay.validate(passed=True) == offline
    assert all(group.samples == 0 for group in coverage.groups)
    replay.commit()
    assert coverage.transitions.samples > 0
    with pytest.raises(RuntimeError):
        replay.commit()
    with pytest.raises(RuntimeError):
        replay.observe({})


def test_stream_matches_offline_bypass_summary_and_checks_last_state():
    trace = useful_trace()
    offline = IntegratedCoverage().collect(trace)
    coverage = IntegratedCoverage()
    replay = coverage.stream()
    for frame in trace['records']:
        replay.observe(frame)
    assert replay.validate(passed=True) == offline
    assert all(group.samples == 0 for group in (coverage.sources, coverage.useful, coverage.ring))
    replay.commit()
    assert coverage.useful.samples > 0


@pytest.mark.parametrize('fault', ('counter_neighbor', 'plru_neighbor', 'gap', 'phase', 'reset'))
def test_late_counter_fault_invalidates_all_pending_credit(fault):
    trace = full_path_trace()
    last = trace['records'][-1]
    if fault == 'counter_neighbor':
        last['abtb']['cells'][1023] ^= 1
    elif fault == 'plru_neighbor':
        last['abtb']['replacers'][3]['states'][63] ^= 1
    elif fault == 'gap':
        last['tick'] += 2
    elif fault == 'phase':
        trace['records'].pop(-2)
    else:
        trace['preedge_records'][0]['reset'] = 0
    coverage = CounterCoverage()
    replay = coverage.stream()
    with pytest.raises(ScoreboardMismatch):
        feed_counter(replay, trace)
    with pytest.raises(ScoreboardMismatch):
        replay.commit()
    assert all(group.samples == 0 for group in coverage.groups)


def test_valid_counter_cannot_commit_if_other_independent_validator_fails():
    session = CounterCaseCoverage()
    feed_counter(session.counter_replay, full_path_trace())
    trace = useful_trace()
    trace['records'][-1]['value']['tables'][1]['state']['useful'][511] ^= 1
    with pytest.raises(ScoreboardMismatch):
        for frame in trace['records']:
            session.bypass_replay.observe(frame)
    with pytest.raises(ScoreboardMismatch):
        session.validate(dict(passed=True))
    assert all(group.samples == 0 for group in session.counter.groups)
    assert session.bypass.useful.samples == 0
    session.abort()


def test_late_scenario_failure_and_empty_stream_cannot_publish():
    coverage = CounterCoverage()
    replay = coverage.stream()
    feed_counter(replay, full_path_trace())
    with pytest.raises(ValueError):
        replay.finish(passed=False)
    with pytest.raises(RuntimeError):
        replay.commit()
    assert all(group.samples == 0 for group in coverage.groups)
    with pytest.raises(ValueError):
        CounterCoverage().stream().finish(passed=True)


def test_unconfirmed_final_input_remains_uncredited_in_stream():
    from tests.bpu.scoreboard.integrated.test_abtb_counter_coverage import counter_trace
    trace = counter_trace([dict(), dict(valid=0)])
    trace['records'].pop()
    coverage = CounterCoverage()
    replay = coverage.stream()
    feed_counter(replay, trace)
    summary = replay.finish(passed=True)
    assert summary['transition_counts'] == {}
    assert summary['unobserved_final_input_events_not_credited'] == 1
