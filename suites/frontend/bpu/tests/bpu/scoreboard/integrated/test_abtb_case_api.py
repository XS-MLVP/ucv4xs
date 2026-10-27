"""Intent API rejects unsupported scope and never exports a failed case."""
from pathlib import Path
from heapq import merge
import ast

import pytest
from toffee import ScoreboardMismatch
from bpuverify.bpu.case.abtb import cases
from tests.bpu.scoreboard.integrated.test_abtb_counter_coverage import full_path_trace
from tests.bpu.scoreboard.integrated.test_coverage_collection import useful_trace


def successful_trace(*, ways=(0, 1, 2, 3), **coordinates):
    return dict(full_path_trace(ways=ways, **coordinates), bypass_records=useful_trace()['records'])


def stream_trace(coverage, trace):
    for tick, phase, row in merge(
            ((row['tick'], 'preedge', row) for row in trace['preedge_records']),
            ((row['tick'], 'rising', row) for row in trace['records'])):
        coverage.observe_abtb(phase, tick, row)
    for row in trace['bypass_records']:
        coverage.observe_bypass(row['phase'], row['tick'], row['value'])
    return trace


@pytest.mark.parametrize('kind,bank,entry_set', (
    ('ready_valid', 0, 0), ('five_alias', True, 0), ('five_alias', 0, True),
    ('five_alias', 4, 0), ('five_alias', 0, 64), ('five_alias', 1.0, 0),
    ('final_not_taken', -1, 1), ('final_not_taken', 3, 64)))
async def test_unsupported_intent_fails_before_any_stimulus_or_artifact(tmp_path, kind, bank, entry_set):
    with pytest.raises(ValueError):
        await cases.check_counter_case(object(), tmp_path, kind=kind, bank=bank, entry_set=entry_set)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('kind', ('five_alias', 'final_not_taken', 'later_taken'))
async def test_repeated_cases_preserve_both_complete_trace_artifacts(monkeypatch, tmp_path, kind):
    calls = []
    async def scenario(agent, output, **kwargs):
        calls.append((output, kwargs))
        (output / 'trace.json').write_text('immutable complete witness')
        return stream_trace(kwargs['coverage'], successful_trace())
    monkeypatch.setitem(cases._RUNNERS, kind, scenario)
    first = await cases.check_counter_case(object(), tmp_path, kind=kind, bank=2, entry_set=31)
    second = await cases.check_counter_case(object(), tmp_path, kind=kind, bank=2, entry_set=31)
    assert first['artifact'] != second['artifact']
    assert all((Path(result['artifact']) / 'trace.json').read_text() == 'immutable complete witness'
        for result in (first, second))
    assert all(kwargs['bank'] == 2 and kwargs['entry_set'] == 31
        and isinstance(kwargs['coverage'], cases.CounterCaseCoverage) for _, kwargs in calls)
    assert first['counter']['transition_total_bins'] == 12288
    assert len(list(tmp_path.glob('functional-coverage*.json'))) == 2
    assert not first['full_matrix_or_FTQ_closed']
    if kind in ('final_not_taken', 'later_taken'):
        assert first['required_paths']['covered_paths'] == 32


@pytest.mark.parametrize('failure', ('scenario', 'late_counter', 'late_bypass', 'failed_trace'))
async def test_no_functional_report_is_exported_when_any_check_fails(monkeypatch, tmp_path, failure):
    async def scenario(agent, output, **kwargs):
        if failure == 'scenario':
            raise AssertionError('live checker failure')
        trace = successful_trace()
        if failure == 'late_counter':
            trace['records'][-1]['abtb']['cells'][1023] ^= 1
        elif failure == 'late_bypass':
            trace['bypass_records'][-1]['value']['tables'][1]['state']['useful'][511] ^= 1
        else:
            trace['passed'] = False
        return stream_trace(kwargs['coverage'], trace)
    monkeypatch.setitem(cases._RUNNERS, 'five_alias', scenario)
    with pytest.raises((AssertionError, ScoreboardMismatch, ValueError)):
        await cases.check_counter_case(object(), tmp_path, kind='five_alias', bank=2, entry_set=31)
    assert not list(tmp_path.glob('functional-coverage*.json'))


def test_both_counter_scenarios_require_all256_physical_coordinates():
    assert set(cases.ALL_CASES) == {(bank, entry_set) for bank in range(4) for entry_set in range(64)}
    assert set(cases.FINAL_NOT_TAKEN_CASES) == set(cases.ALL_CASES)


async def test_timing_io_failure_cannot_mask_primary_checker_failure(monkeypatch, tmp_path):
    primary = AssertionError('live checker failure at counter[1023]')
    async def scenario(agent, output, **kwargs):
        raise primary
    def fail_save(self, path, *, passed):
        raise OSError('timing output unavailable')
    monkeypatch.setitem(cases._RUNNERS, 'five_alias', scenario)
    monkeypatch.setattr(cases.CaseTiming, 'save', fail_save)
    with pytest.raises(AssertionError) as caught:
        await cases.check_counter_case(object(), tmp_path, kind='five_alias', bank=0, entry_set=0)
    assert caught.value is primary
    assert any('timing output unavailable' in note for note in primary.__notes__)
    assert not list(tmp_path.glob('functional-coverage*.json'))


@pytest.mark.parametrize('bank,entry_set', ((0, 0), (1, 1), (2, 31), (3, 62), (3, 63)))
async def test_finalNT_api_accepts_bounds_and_previously_unregistered_coordinates(monkeypatch, tmp_path, bank, entry_set):
    async def scenario(agent, output, **kwargs):
        return stream_trace(kwargs['coverage'], successful_trace(bank=bank, set_index=entry_set))
    monkeypatch.setitem(cases._RUNNERS, 'final_not_taken', scenario)
    result = await cases.check_counter_case(object(), tmp_path,
        kind='final_not_taken', bank=bank, entry_set=entry_set)
    assert result['required_paths']['covered_paths'] == 32
    assert result['required_paths']['bank'] == bank
    assert result['required_paths']['entry_set'] == entry_set


@pytest.mark.parametrize('kind', ('final_not_taken', 'later_taken'))
@pytest.mark.parametrize('missing_way', range(4))
async def test_partial_way_coverage_cannot_export_either_functional_report(monkeypatch, tmp_path, missing_way, kind):
    async def scenario(agent, output, **kwargs):
        return stream_trace(kwargs['coverage'], successful_trace(ways=tuple(way for way in range(4) if way != missing_way)))
    monkeypatch.setitem(cases._RUNNERS, kind, scenario)
    with pytest.raises(ScoreboardMismatch) as error:
        await cases.check_counter_case(object(), tmp_path,
            kind=kind, bank=2, entry_set=31)
    assert 'required_physical_counter_paths' in str(error.value)
    assert f'bank2.set31.way{missing_way}' in str(error.value)
    assert not list(tmp_path.glob('functional-coverage*.json'))


def test_scenarios_share_one_full_write_checker_and_observation_lifecycle():
    from bpuverify.bpu.case.abtb import alias as alias_scenario
    from bpuverify.bpu.case.abtb import final_not_taken as final_not_taken_scenario
    from bpuverify.bpu.case.abtb import later_taken as later_taken_scenario
    from bpuverify.bpu.env.abtb.write import WriteObservation
    assert alias_scenario.PairObservation is final_not_taken_scenario.NegativePairObservation is later_taken_scenario.NegativePairObservation is WriteObservation
    for module in (alias_scenario, final_not_taken_scenario, later_taken_scenario):
        tree = ast.parse(Path(module.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node.func, ast.Attribute) else '')
                assert name not in {'FallingEdge', 'RisingEdge', 'ClockCycles', 'get_', 'set_',
                    'GetInternalSignal', 'GetInternalSignalList', 'gather'}
