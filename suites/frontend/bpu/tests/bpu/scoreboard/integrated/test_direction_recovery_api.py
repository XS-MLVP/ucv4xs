"""Recovery coverage cannot substitute for or bypass steady four-way checks."""
import inspect

import pytest
from toffee import ScoreboardMismatch

from bpuverify.bpu.case.abtb import recovery_cases
from bpuverify.bpu.case.abtb.final_not_taken import run_final_not_taken_cycle
from tests.bpu.scoreboard.integrated.test_abtb_counter_coverage import full_path_trace
from tests.bpu.scoreboard.integrated.test_shadow_selection_coverage import selection_trace


@pytest.mark.parametrize('coordinates', [dict(bank=True, entry_set=63, table=1, slot=2),
    dict(bank=3, entry_set=64, table=1, slot=2), dict(bank=3, entry_set=63, table=True, slot=2),
    dict(bank=3, entry_set=63, table=1, slot=8)])
async def test_invalid_recovery_scope_does_not_drive_or_create_output(tmp_path, coordinates):
    with pytest.raises(ValueError):
        await recovery_cases.check_direction_recovery_case(object(), tmp_path, **coordinates)
    assert not list(tmp_path.iterdir())


async def test_invalid_preparation_mode_fails_before_reset_or_observation(tmp_path):
    with pytest.raises(ValueError, match='direction preparation'):
        await run_final_not_taken_cycle(object(), tmp_path, bank=3, entry_set=63, direction_preparation='queue')
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('fault', (None, 'scenario', 'payload', 'absent_fallback'))
async def test_recovery_api_preserves_all_replays_and_exports_only_after_required_fallback(tmp_path, monkeypatch, fault):
    calls, exports = [], []
    async def scenario(agent, output, **kwargs):
        calls.append(kwargs)
        if fault == 'scenario': raise AssertionError('live checker failure')
        trace = dict(full_path_trace(), **selection_trace())
        if fault == 'payload': trace['bypass_records'][-1]['value']['tables'][1]['outputs']['response']['tag'] ^= 1
        elif fault == 'absent_fallback': trace['bypass_records'] = trace['bypass_records'][:-2]
        return trace
    monkeypatch.setattr(recovery_cases, 'run_final_not_taken_cycle', scenario)
    for kind in ('IntegratedCoverage', 'CounterCoverage', 'ResponseSelectionCoverage'):
        monkeypatch.setattr(getattr(recovery_cases, kind), 'save',
            lambda self, output, *, case, kind=kind: exports.append((kind, case)))
    if fault:
        with pytest.raises((AssertionError, ScoreboardMismatch)):
            await recovery_cases.check_direction_recovery_case(object(), tmp_path,
                bank=3, entry_set=63, table=1, slot=2)
        assert not exports
    else:
        result = await recovery_cases.check_direction_recovery_case(object(), tmp_path,
            bank=3, entry_set=63, table=1, slot=2)
        assert len(exports) == 3
        assert result['selection']['occurrences']['table1.slot2.fallback'] == 1
        assert not result['steady_four_way_residency_claimed'] and not result['full_matrix_or_FTQ_closed']
    assert calls == [dict(bank=3, entry_set=63, direction_preparation='redirect')]


def test_existing_all256_workflow_still_defaults_to_steady_residency():
    assert inspect.signature(run_final_not_taken_cycle).parameters['direction_preparation'].default == 'resident'
