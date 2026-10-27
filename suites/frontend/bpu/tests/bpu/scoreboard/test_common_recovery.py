"""Synthetic fault qualification is not DUT coverage or a hardware PASS."""
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.checker.common_recovery import CommonRecoveryChecks
from bpuverify.bpu.coverage.common_recovery import CommonRecoveryCoverage
from bpuverify.bpu.model.common_history import Block, GHR_WIDTH, Value
from bpuverify.bpu.model.common_recovery import PC, POSITIONS, PROFILES
from bpuverify.bpu.model.selection import Branch, Kind
from bpuverify.bpu.transaction.types import BpuRedirect
from tests.bpu.scoreboard.test_owned_common_history import fixture as base_fixture, sample


@pytest.mark.parametrize('profile', PROFILES, ids=lambda p: p.name)
def test_normal_conditional_sequences_reach_declared_patterns_and_closed_recovery_values(profile):
    value = Value()
    block = Block(PC, POSITIONS)
    for _ in range(GHR_WIDTH):
        value = value.append(block.outcomes(profile.loop_choice), valid=True)
    assert value == profile.original
    assert profile.recover(value) == profile.restored
    assert profile.consumer == Value(True, profile.restored.ghr, profile.restored.bw)
    assert value.append(block.outcomes(profile.loop_choice), valid=True) == value


def fixture(profile):
    old, actual, _, receipt, _ = base_fixture()
    coverage = CommonRecoveryCoverage(profile)
    checks = CommonRecoveryChecks(old.pipeline, profile=profile, coverage=coverage)
    checks.initialized = True
    checks.last_tick = 100
    for _ in range(GHR_WIDTH):
        checks.model.advance(completed=(Block(PC, POSITIONS), profile.loop_choice))
    token = actual.token
    checkpoint = checks.model.checkpoint(token.history, Block.from_token(token))
    checks.sources[token.history.sequence] = checkpoint
    original = receipt(token, checkpoint.value)
    original.prediction = NS(start_pc=PC)
    checks.original_source(original)
    correction = profile.correction
    request = BpuRedirect(correction.target, original.meta.redirect,
        cfi_pc=PC + correction.position, taken=int(correction.taken), branch_type=int(correction.kind))
    checks.plan(original, request)
    m = original.meta.redirect['commonHRMeta']
    accepted = dict(valid=1, pc=PC + correction.position, target=correction.target,
        taken=int(correction.taken), kind=int(correction.kind), meta=dict(ghr=m['ghr'], bw=m['bw'],
        hits=m['hitMask'], positions=m['position'], kinds=tuple(a['branchType'] for a in m['attribute'])))
    return checks, original, accepted, receipt


def restored(checks, accepted):
    sample(checks, 100, redirect=accepted)
    sample(checks, 102)
    sample(checks, 104)
    checks.recovered(100)


def consumer(checks, original, receipt):
    target = checks.profile.correction.target
    checks.model.advance(completed=(Block(target), Branch(5, target, Kind.DIRECT, True)))
    token = replace(original.token, pc=target, lookup=None,
        history=replace(original.token.history, sequence=original.token.history.sequence + 1000))
    cp = checks.model.checkpoint(token.history, Block.from_token(token))
    checks.sources[token.history.sequence] = cp
    actual = receipt(token, cp.value, pred=110, at=114)
    actual.prediction = NS(start_pc=target)
    return actual


@pytest.mark.parametrize('profile', PROFILES, ids=lambda p: p.name)
def test_both_real_endpoints_and_complete_immutable_original_are_required_before_checked(profile):
    checks, original, accepted, receipt = fixture(profile)
    restored(checks, accepted)
    assert checks.coverage.groups['checked'].coverage == 0
    fresh = consumer(checks, original, receipt)
    checks.consumed(fresh)
    assert checks.coverage.groups['checked'].coverage == 0
    checks.finish()
    assert all(group.coverage == 100 for group in checks.coverage.groups.values())
    assert checks.coverage.witnesses[checks.rules[3]]['actual_committed']['state'] == profile.restored.mapping()
    assert checks.coverage.witnesses[checks.rules[4]]['actual'] == profile.consumer.mapping()


@pytest.mark.parametrize('profile', PROFILES, ids=lambda p: p.name)
@pytest.mark.parametrize('fault', ('ghr', 'bw', 'position', 'target', 'taken', 'kind', 'hits'))
def test_corrupt_actual_recovery_cannot_advance_reference_or_gain_checked(profile, fault):
    checks, _, accepted, _ = fixture(profile)
    if fault in ('ghr', 'bw'):
        accepted['meta'][fault] ^= 1
    elif fault == 'hits':
        accepted['meta']['hits'] = (0, 0, 0, 0)
    else:
        accepted['pc' if fault == 'position' else fault] ^= 1
    before = checks.model.value, checks.model.pending, len(checks.plans)
    with pytest.raises(AssertionError) as first:
        sample(checks, 100, redirect=accepted)
    with pytest.raises(AssertionError) as second:
        checks.raise_failure()
    assert first.value is second.value
    assert (checks.model.value, checks.model.pending, len(checks.plans)) == before
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES, ids=lambda p: p.name)
@pytest.mark.parametrize('fault', ('ghr', 'bw', 'valid'))
def test_wrong_committed_prefix_is_rejected_even_if_the_plan_itself_was_correct(profile, fault):
    checks, _, accepted, _ = fixture(profile)
    sample(checks, 100, redirect=accepted)
    sample(checks, 102)
    state = checks.profile.restored
    state = replace(state, **{fault: not state.valid if fault == 'valid' else getattr(state, fault) ^ 1})
    with pytest.raises(AssertionError):
        sample(checks, 104, state=state)
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES, ids=lambda p: p.name)
@pytest.mark.parametrize('fault', ('ghr', 'bw', 'valid', 'wrong-pc', 'old-tick', 'foreign-owner'))
def test_bad_public_consumer_cannot_close_a_correct_internal_recovery(profile, fault):
    checks, original, accepted, receipt = fixture(profile)
    restored(checks, accepted)
    actual = consumer(checks, original, receipt)
    if fault in ('ghr', 'bw', 'valid'):
        actual.meta.resolve['commonHR'][fault] ^= 1
    elif fault == 'wrong-pc':
        actual.prediction.start_pc ^= 0x10
    elif fault == 'old-tick':
        actual.prediction_tick = 100
    else:
        actual.token = replace(actual.token, history=replace(actual.token.history))
    with pytest.raises(AssertionError):
        checks.consumed(actual)
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES, ids=lambda p: p.name)
def test_missing_public_consumer_is_not_hidden_by_committed_state_success(profile):
    checks, _, accepted, _ = fixture(profile)
    restored(checks, accepted)
    with pytest.raises(AssertionError, match='consumer'):
        checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES, ids=lambda p: p.name)
def test_unrelated_original_metadata_mutation_is_not_hidden_by_unchanged_common_history(profile):
    checks, original, accepted, receipt = fixture(profile)
    restored(checks, accepted)
    checks.consumed(consumer(checks, original, receipt))
    original.meta.resolve['unrelated-source-field'] = 1
    with pytest.raises(AssertionError, match='immutable'):
        checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


def test_unregistered_profiles_cannot_silently_create_a_new_coverage_contract():
    foreign = replace(PROFILES[0], name='unreviewed-profile')
    with pytest.raises(ValueError, match='unknown'):
        CommonRecoveryCoverage(foreign)
    old, _, _, _, _ = base_fixture()
    with pytest.raises(ValueError, match='unknown'):
        CommonRecoveryChecks(old.pipeline, profile=foreign)


@pytest.mark.parametrize('profile', PROFILES, ids=lambda p: p.name)
def test_reset_expires_original_and_actual_endpoint_proof_together(profile):
    checks, _, accepted, _ = fixture(profile)
    restored(checks, accepted)
    checks.capture_state(NS(tick=106), dict(reset=1))
    assert checks.original_snapshot is checks.actual_recovery is checks.committed_sample is None
    with pytest.raises(AssertionError, match='reset epoch'):
        checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0
