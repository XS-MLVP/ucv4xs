"""Coverage requires observed effects, full replay and an atomic successful commit."""
from copy import deepcopy
import ast
import importlib
from pathlib import Path
import sys

import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.bpu.model.bypass.model import BypassReference
from suites.frontend.bpu.bpu.coverage.bypass.supplemental import IntegratedCoverage
from suites.frontend.bpu.bpu.coverage.bypass.supplemental import OPERATIONS
from suites.frontend.bpu.bpu.coverage.bypass.supplemental import SOURCES


def inputs(**changes):
    value = dict(read_index=0, train_index=0, tag=0, allocate=0,
        allocate_taken=0, allocate_position=0, update=0, update_taken=0,
        update_position=0, update_counter=0, useful_valid=0, useful_increase=0, age=0)
    value.update(changes)
    return value


def trace_for(steps):
    references = [BypassReference(0), BypassReference(1)]
    frames = []
    for reset, boundaries in [(1, [inputs(), inputs()])] + steps:
        frame = dict(phase='preedge', tick=len(frames) + 1, value=dict(reset=reset,
            tables=[dict(inputs=deepcopy(boundary), state=ref.state())
                    for ref, boundary in zip(references, boundaries, strict=True)]))
        frames.append(frame)
        for ref, boundary in zip(references, boundaries, strict=True):
            ref.advance(boundary, reset=bool(reset))
        frames.append(dict(phase='rising', tick=len(frames) + 1, value=dict(reset=reset,
            tables=[dict(inputs=deepcopy(boundary), state=ref.state())
                    for ref, boundary in zip(references, boundaries, strict=True)])))
    return dict(passed=True, records=frames, writes=[dict(source='invented-cached-expectation')])


def useful_trace():
    steps = [(0, [inputs(allocate=1), inputs(allocate=1)])]
    steps += [(0, [inputs(update=1, useful_valid=1, useful_increase=1)] * 2)] * 4
    steps += [(0, [inputs(update=1, useful_valid=1)] * 2)] * 4
    steps += [(0, [inputs(age=1)] * 2), (0, [inputs(allocate=1)] * 2),
              (0, [inputs(age=1, update=1, useful_valid=1, useful_increase=1)] * 2)]
    return trace_for(steps)


def test_complete_operation_denominator_and_honest_partial_coverage():
    coverage = IntegratedCoverage()
    summary = coverage.collect(useful_trace())
    assert summary['source_total_bins'] == 4 * 2 * len(SOURCES) == 24
    assert summary['useful_total_bins'] == 2 * 4 * len(OPERATIONS) == 56
    assert summary['useful_counts']['table0.bank0.age_nonzero'] == 1
    assert summary['useful_counts']['table1.bank0.age_nonzero'] == 1
    assert summary['useful_counts']['table0.bank0.increment'] == 2
    assert summary['useful_counts']['table1.bank0.increment'] == 1
    assert summary['useful_counts']['table0.bank0.saturated_high_hold'] == 2
    assert summary['useful_counts']['table1.bank0.saturated_high_hold'] == 3
    assert summary['useful_bins'] < 56
    assert coverage.useful.coverage < 100
    assert not summary['all_addresses_or_overlap_or_full_FTQ_claimed']


@pytest.mark.parametrize('fault', ('useful', 'neighbor', 'counter', 'status', 'selection', 'phase', 'gap', 'reset'))
def test_late_fault_raises_contextual_failure_without_any_coverage(fault):
    trace = useful_trace()
    frame = trace['records'][-1]
    state = frame['value']['tables'][1]['state']
    if fault == 'useful':
        state['useful'][0] ^= 1
    elif fault == 'neighbor':
        state['useful'][511] ^= 1
    elif fault == 'counter':
        state['cells'][0]['counter'] ^= 1
    elif fault == 'status':
        state['status'][0]['dirty'] ^= 1
    elif fault == 'selection':
        state['chosen'] ^= 1
    elif fault == 'phase':
        frame['phase'] = 'preedge'
    elif fault == 'gap':
        frame['tick'] += 2
    else:
        trace['records'][0]['value']['reset'] = 0
    coverage = IntegratedCoverage()
    with pytest.raises(ScoreboardMismatch):
        coverage.collect(trace)
    assert all(group.samples == 0 for group in (coverage.sources, coverage.useful, coverage.ring))


def test_final_input_without_observed_effect_gets_no_credit():
    trace = trace_for([(0, [inputs(allocate=1), inputs(allocate=1)])])
    trace['records'].pop()
    coverage = IntegratedCoverage()
    result = coverage.collect(trace)
    assert result['source_bins'] == result['useful_bins'] == 0
    assert result['unobserved_final_preedge_operations_not_credited'] > 0


@pytest.mark.parametrize('field', ('passed', 'failure', 'records'))
def test_failed_or_empty_report_is_rejected(field):
    trace = useful_trace()
    trace[field] = False if field == 'passed' else 'failure' if field == 'failure' else []
    with pytest.raises(ValueError):
        IntegratedCoverage().collect(trace)


def test_cached_flags_and_writes_are_not_a_source_of_bin_hits():
    trace = useful_trace()
    expected = IntegratedCoverage().collect(trace)
    trace['writes'] = [dict(table=1, index=511, source='captured_counter')] * 100
    trace['expected'] = dict(all_bins_hit=True)
    assert IntegratedCoverage().collect(trace) == expected


def test_complete_dependency_closure_including_local_imports():
    root = Path(importlib.import_module('suites.frontend.bpu.bpu').__file__).resolve().parent
    for path in root.rglob('*.py'):
        module = 'suites.frontend.bpu.bpu.' + '.'.join(path.relative_to(root).with_suffix('').parts)
        if module.endswith('.__init__'):
            module = module.removesuffix('.__init__')
        importlib.import_module(module)
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert (node.module.startswith('suites.frontend.bpu.')
                        or node.module.split('.')[0] in sys.stdlib_module_names | {'toffee', 'pytest'})
            elif isinstance(node, ast.Import):
                assert all(item.name.startswith('suites.frontend.bpu.')
                           or item.name.split('.')[0] in sys.stdlib_module_names | {'toffee', 'pytest'}
                           for item in node.names)


@pytest.mark.asyncio
async def test_case_api_publishes_only_after_real_effect_replay(monkeypatch, tmp_path):
    from suites.frontend.bpu.bpu.case.bypass import cases
    from tests.bpu.scoreboard.integrated.test_abtb_counter_coverage import full_path_trace
    from tests.bpu.scoreboard.integrated.test_shadow_selection_coverage import selection_trace
    async def scenario(agent, output, **kwargs):
        assert kwargs == dict(bank=0)
        return dict(useful_trace(), **selection_trace(), counter_trace=full_path_trace())
    monkeypatch.setitem(cases._RUNNERS, 'natural', scenario)
    result = await cases.check_integrated_case(object(), tmp_path, kind='natural', bank=0)
    assert result['source_bins'] > 0
    assert result['abtb_counter']['transition_total_bins'] == 12288
    assert (tmp_path / 'functional-coverage-integrated-natural-0.json').is_file()
    assert (tmp_path / 'functional-coverage-integrated-abtb-natural-0.json').is_file()
    assert result['response_selection']['bins_hit'] > 0
    assert (tmp_path / 'functional-coverage-shadow-response-selection-natural-0.json').is_file()


@pytest.mark.asyncio
async def test_counter_failure_prevents_both_coverage_reports(monkeypatch, tmp_path):
    from suites.frontend.bpu.bpu.case.bypass import cases
    from tests.bpu.scoreboard.integrated.test_abtb_counter_coverage import full_path_trace
    from tests.bpu.scoreboard.integrated.test_shadow_selection_coverage import selection_trace
    async def scenario(agent, output, **kwargs):
        counter = full_path_trace()
        counter['records'][-1]['abtb']['cells'][1023] ^= 1
        return dict(useful_trace(), **selection_trace(), counter_trace=counter)
    monkeypatch.setitem(cases._RUNNERS, 'natural', scenario)
    with pytest.raises(ScoreboardMismatch):
        await cases.check_integrated_case(object(), tmp_path, kind='natural', bank=0)
    assert not list(tmp_path.glob('functional-coverage*.json'))


@pytest.mark.asyncio
async def test_case_api_never_publishes_a_failed_scenario(monkeypatch, tmp_path):
    from suites.frontend.bpu.bpu.case.bypass import cases
    async def scenario(agent, output, **kwargs):
        raise AssertionError('real checker mismatch')
    monkeypatch.setitem(cases._RUNNERS, 'natural', scenario)
    with pytest.raises(AssertionError, match='real checker mismatch'):
        await cases.check_integrated_case(object(), tmp_path, kind='natural', bank=0)
    assert not list(tmp_path.glob('functional-coverage*.json'))


@pytest.mark.asyncio
async def test_unknown_intent_rejected_before_stimulus(tmp_path):
    from suites.frontend.bpu.bpu.case.bypass.cases import check_integrated_case
    with pytest.raises(ValueError, match='unsupported integrated intent'):
        await check_integrated_case(object(), tmp_path, kind='ready_valid', bank=0)
    assert not list(tmp_path.iterdir())
