"""Pure checker qualification; never hardware or native-coverage credit."""
import pytest

from bpuverify.bpu.model.sc_early_learning import PROFILES,RULES
from bpuverify.bpu.coverage.sc_early_learning import Coverage
from tests.bpu.scoreboard._sc_early_program import Program


@pytest.mark.parametrize('profile',PROFILES)
async def test_real_original_guidance_and_newer_consumer_feedback_have_separate_witnesses(profile):
    p = Program(profile)
    await p.complete()
    c = p.checks
    assert c.coverage.groups['checked'].coverage==0
    result = c.finish()
    assert c.closed and set(c.reached_rules)==set(RULES)
    assert result['confirmed']['owner']!=result['consumer_own_confirmation']['owner']
    assert result['consumer_own_confirmation']['new_useful']==0
    assert result['confirmed']['index']==result['new_b']['provider']['index']


@pytest.mark.parametrize('fault',('original-state','newer-state','original-owner','public-metadata'))
async def test_wrong_actual_learning_or_rebound_original_never_grants_hardware_credit(fault):
    p = Program('conditional-entry.held')
    c = p.checks
    if fault.endswith('state'):
        def mutate(actual):
            pending = c.pending if fault=='original-state' else c.consumer_pending
            if pending is not None:
                rows = [list(row) for row in actual['useful']]
                rows[0][pending['index']] = 0 if fault=='original-state' else 1
                actual['useful'] = tuple(tuple(row) for row in rows)
        p.mutate = mutate
        with pytest.raises(AssertionError):
            await p.complete()
    else:
        await p.complete()
        if fault=='original-owner':
            c.confirmed['owner'] = c.consumer_confirmed['owner']
        else:
            c.teacher.meta['wrong-owner'] = True
        with pytest.raises(AssertionError):
            c.finish()
    assert not c.closed and c.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('missing',RULES)
def test_missing_behavior_obligation_cannot_close_checked_coverage(missing):
    coverage = Coverage(PROFILES[0])
    for rule in RULES:
        if rule!=missing:
            coverage.record('reached',rule,10)
            coverage.record('checked',rule,12)
    with pytest.raises(AssertionError):
        coverage.finish()
    assert not coverage.closed and coverage.groups['checked'].coverage==0
