"""Intent wrapper preserves the admitted depth8 bound and never hides failure."""
import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.bpu.case.ras import cases


def report(kind, count):
    actions = [2, 2, 1, 1] if kind == 'nested' else (
        [2] * count + [1] * min(count, 7) if kind == 'deep' else [2] * (count + 1))
    accepted = [dict(request=dict(action=action)) for action in actions]
    return dict(accepted=accepted, applied=[{} for _ in actions], actual_calls=len(actions),
                summary=dict(accepted=len(actions), applied=len(actions)))


@pytest.mark.parametrize('kind,count,total', (
    ('nested', 0, 4), ('deep', 4, 8), ('deep', 7, 14), ('deep', 8, 15),
    ('repeat', 9, 10), ('repeat', 10, 11)))
async def test_all_six_intents_publish_only_actual_accepted_actions(monkeypatch, tmp_path, kind, count, total):
    async def stimulus(agent, *args):
        assert args == (() if kind == 'nested' else (count,))
        return report(kind, count)
    name = dict(nested='run_nested', deep='run_chain', repeat='run_repeated_calls')[kind]
    monkeypatch.setattr(cases, name, stimulus)
    summary = await cases.check_retirement_case(object(), tmp_path, kind=kind, count=count)
    assert summary['accepted'] == summary['applied'] == total
    assert (tmp_path / f'functional-coverage-integrated-retirement-{kind}-{count}.json').is_file()


@pytest.mark.parametrize('fault', ('drain', 'accepted_count', 'applied_count', 'program_count', 'action'))
async def test_failed_retirement_never_publishes_coverage(monkeypatch, tmp_path, fault):
    trace = report('nested', 0)
    if fault == 'drain':
        trace['applied'].pop()
    elif fault == 'accepted_count':
        trace['summary']['accepted'] += 1
    elif fault == 'applied_count':
        trace['summary']['applied'] += 1
    elif fault == 'program_count':
        trace['accepted'].pop()
        trace['applied'].pop()
        trace['summary'] = dict(accepted=3, applied=3)
    else:
        trace['accepted'][0]['request']['action'] = 0
    async def stimulus(agent):
        return trace
    monkeypatch.setattr(cases, 'run_nested', stimulus)
    with pytest.raises((ScoreboardMismatch, ValueError)):
        await cases.check_retirement_case(object(), tmp_path, kind='nested')
    assert not list(tmp_path.iterdir())


async def test_real_checker_exception_propagates(monkeypatch, tmp_path):
    async def stimulus(agent):
        raise AssertionError('source association mismatch')
    monkeypatch.setattr(cases, 'run_nested', stimulus)
    with pytest.raises(AssertionError, match='source association mismatch'):
        await cases.check_retirement_case(object(), tmp_path, kind='nested')
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('kind,count', (('deep', 9), ('repeat', 8), ('nested', 1)))
async def test_unqualified_modes_rejected(tmp_path, kind, count):
    with pytest.raises(ValueError, match='unsupported retirement intent'):
        await cases.check_retirement_case(object(), tmp_path, kind=kind, count=count)
