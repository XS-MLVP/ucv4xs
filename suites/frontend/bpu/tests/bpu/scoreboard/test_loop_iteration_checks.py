"""Synthetic iteration fault injection is checker qualification, not DUT coverage."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from toffee import Scoreboard

from bpuverify.bpu.checker.loop_iteration import LoopIterationChecks
from bpuverify.bpu.coverage.loop_iteration import LoopIterationCoverage, FinalIterationCoverage
from bpuverify.bpu.model.loop_iteration import PROGRAMS, MAX_ITERATIONS
from bpuverify.bpu.transaction.types import BpuRedirect
from tests.bpu.scoreboard.test_loop_iteration_model import natural, cycle, stage_token, token, BACK, PC


def fixture():
    model, current, sources = natural(MAX_ITERATIONS)
    token = stage_token(sources[5])
    receipt = NS(token=token, meta=NS(redirect={'commonHRMeta': {'imli': 5}}, resolve={'commonHR': {'imli': 5}}))
    pipeline = NS(board=Scoreboard('synthetic.loop-iteration'), raise_failure=lambda: None,
        source_token=lambda r: r.token, last_tick=100,
        last_cycle=cycle(tokens=(current, None, None), branches=(BACK, None, None)),
        last_events=NS(redirect=NS(source=token.history)))
    checks = LoopIterationChecks(pipeline, coverage=LoopIterationCoverage(PROGRAMS[0]))
    checks.initialized = True; checks.model = model
    request = BpuRedirect(PC, receipt.meta.redirect, cfi_pc=PC+1, branch_type=1)
    checks.plan(receipt, request)
    row = dict(reset=0, state=MAX_ITERATIONS, lookup=6, stages=(MAX_ITERATIONS, 0, 0), repairs=(0, 0),
        redirect=dict(valid=1, pc=PC+1, target=PC, taken=1, kind=1, count=5))
    return checks, row, receipt


def test_actual_accepted_recovery_and_following_registration_are_both_compared():
    checks, row, _ = fixture()
    checks.capture_state(NS(tick=100), row); checks.raise_failure()
    assert checks.model.cursor == 6 and checks.last_recovery['registered'] is False and not checks.plans
    checks.pipeline.last_tick = 102
    checks.pipeline.last_cycle = cycle()
    row.update(state=6, lookup=6, stages=(0, 0, 0)); row['redirect']['valid'] = 0
    checks.capture_state(NS(tick=102), row); checks.raise_failure()
    assert checks.last_recovery['registered'] is True
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('registered-state', 'lookup-current-not-original', 'stage-snapshot',
    'wrong-cfi', 'wrong-target', 'wrong-kind', 'wrong-direction', 'younger-restore-input',
    'equal-encoded-foreign-owner', 'missing-plan', 'unexpected-middle-repair', 'lost-sample'))
def test_faults_raise_the_same_first_exception_without_advancing_or_earning_checked(fault):
    checks, row, receipt = fixture()
    if fault == 'registered-state': row['state'] = 254
    elif fault == 'lookup-current-not-original': row['lookup'] = MAX_ITERATIONS
    elif fault == 'stage-snapshot': row['stages'] = (5, 0, 0)
    elif fault == 'wrong-cfi': row['redirect']['pc'] += 1
    elif fault == 'wrong-target': row['redirect']['target'] += 1
    elif fault == 'wrong-kind': row['redirect']['kind'] = 2
    elif fault == 'wrong-direction': row['redirect']['taken'] = 0
    elif fault == 'younger-restore-input': row['redirect']['count'] = MAX_ITERATIONS
    elif fault == 'equal-encoded-foreign-owner': checks.pipeline.last_events.redirect.source = replace(receipt.token.history)
    elif fault == 'missing-plan': checks.plans.clear()
    elif fault == 'unexpected-middle-repair': row['repairs'] = (1, 0)
    else: checks.pipeline.last_tick = 98
    before = checks.model.state(); planned = tuple(checks.plans)
    checks.capture_state(NS(tick=100), row)
    with pytest.raises(AssertionError) as first: checks.raise_failure()
    with pytest.raises(AssertionError) as second: checks.finish()
    assert first.value is second.value and checks.model.state() == before
    assert tuple(checks.plans) == planned
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('role', ('redirect', 'resolve'))
def test_public_metadata_is_compared_not_used_as_a_model_seed(role):
    checks, _, receipt = fixture()
    wrong = deepcopy(receipt)
    wrong.token = receipt.token
    mapping = wrong.meta.redirect['commonHRMeta'] if role == 'redirect' else wrong.meta.resolve['commonHR']
    mapping['imli'] = MAX_ITERATIONS
    before = checks.model.state()
    with pytest.raises(AssertionError): checks.source(wrong)
    assert checks.model.state() == before and checks.coverage.groups['checked'].coverage == 0


def test_restored_lookup_alone_does_not_replace_the_next_registered_comparison():
    checks, row, _ = fixture()
    checks.capture_state(NS(tick=100), row); checks.raise_failure()
    checks.pipeline.last_tick = 102; checks.pipeline.last_cycle = cycle()
    row.update(state=MAX_ITERATIONS, lookup=6, stages=(0, 0, 0)); row['redirect']['valid'] = 0
    before = checks.model.state()
    checks.capture_state(NS(tick=102), row)
    with pytest.raises(AssertionError): checks.raise_failure()
    assert checks.model.state() == before and not checks.last_recovery['registered']


def test_correct_recovery_without_original_and_consumer_cannot_close_coverage():
    checks, row, _ = fixture()
    checks.capture_state(NS(tick=100), row); checks.raise_failure()
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


def final_fixture():
    checks, row, receipt = fixture()
    checks.coverage = FinalIterationCoverage(); checks.plans.clear()
    receipt.prediction_tick = 10; receipt.meta_tick = 14
    original = receipt, deepcopy(receipt.meta), checks.source(receipt)
    current = stage_token(checks.model.owned[MAX_ITERATIONS])
    new = token(MAX_ITERATIONS + 1)
    wanted = {'0.hasProvider': 1, '0.providerTableIdx': 3, '0.providerTakenCtr_value': 3,
              '0.useProvider': 0, '0.altOrBasePred': 1}
    checks.pipeline.model = NS(stages=(new, None, None), sources=NS(defined_metadata=lambda _: wanted))
    checks.pipeline.last_events.redirect = None
    checks.pipeline.last_cycle = cycle(tokens=(current, None, receipt.token),
        branches=(BACK, None, BACK), early=True, final=True, issue=True)
    row.update(repairs=(0, 1), stages=(MAX_ITERATIONS, 0, 5)); row['redirect']['valid'] = 0
    checks.capture_state(NS(tick=100), row); checks.raise_failure()
    checks.pipeline.last_tick = 102
    checks.pipeline.last_cycle = cycle(tokens=(new, None, None), branches=(BACK, None, None))
    row.update(repairs=(0, 0), stages=(6, 0, 0), state=6, lookup=6)
    checks.capture_state(NS(tick=102), row); checks.raise_failure()
    consumer = NS(token=new, prediction_tick=102, meta_tick=106,
        meta=NS(redirect={'commonHRMeta': {'imli': 6}}, resolve={'commonHR': {'imli': 6}}))
    return checks, original, consumer, wanted


def test_final_repair_wins_over_younger_saturated_early_prediction_and_requires_exact_consumer():
    checks, original, consumer, _ = final_fixture()
    repair = checks.proof['first_final-repair']
    assert (repair['before'], repair['original'], repair['after']) == (MAX_ITERATIONS, 5, 6)
    assert repair['actual_lookup'] == repair['actual_registered'] == 6
    assert checks.coverage.groups['checked'].coverage == 0
    checks.finish_final_repair(original, consumer)
    assert all(g.coverage == 100 for g in checks.coverage.groups.values())
    with pytest.raises(AssertionError, match='single-use'):
        checks.finish_final_repair(original, consumer)


@pytest.mark.parametrize('fault', ('no-actual-repair', 'unregistered-repair', 'wrong-original',
    'equal-count-wrong-consumer', 'metadata-reseed', 'original-mutated', 'no-weak-provider',
    'provider-used-instead-of-opposite-base', 'old-consumer'))
def test_final_repair_qualification_rejects_missing_or_foreign_lifecycle_evidence(fault):
    checks, original, consumer, wanted = final_fixture()
    if fault == 'no-actual-repair': del checks.proof['first_final-repair']
    elif fault == 'unregistered-repair': del checks.proof['first_final-repair']['registered_tick']
    elif fault == 'wrong-original': checks.proof['first_final-repair']['token'] += 1
    elif fault == 'equal-count-wrong-consumer':
        other = token(MAX_ITERATIONS + 2)
        checks.model.advance(cycle(issue=True), issued=other); consumer.token = other
    elif fault == 'metadata-reseed': consumer.meta.redirect['commonHRMeta']['imli'] = MAX_ITERATIONS
    elif fault == 'original-mutated': original[0].meta.resolve['commonHR']['imli'] = 99
    elif fault == 'no-weak-provider': wanted['0.providerTakenCtr_value'] = 0
    elif fault == 'provider-used-instead-of-opposite-base': wanted['0.useProvider'] = 1
    else: consumer.prediction_tick = 100
    before = checks.model.state()
    with pytest.raises(AssertionError) as first: checks.finish_final_repair(original, consumer)
    with pytest.raises(AssertionError) as second: checks.raise_failure()
    assert first.value is second.value and checks.model.state() == before
    assert checks.coverage.groups['checked'].coverage == 0
