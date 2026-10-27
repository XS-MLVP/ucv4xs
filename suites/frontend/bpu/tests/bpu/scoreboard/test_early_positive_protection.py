"""Taken protection programs use synthetic actuals here, never DUT credit."""
import ast
from dataclasses import replace
from pathlib import Path

from bpuverify.bpu.checker.early_positive_protection import EarlyPositiveProtectionChecks
from bpuverify.bpu.coverage.early_positive_protection import EarlyPositiveProtectionCoverage
from bpuverify.bpu.model.early_opposition import resident, ahead_owner, steady_history, main_counter, provider
from bpuverify.bpu.model.early_positive_protection import EDGES, OLDER_PATHS, rules
from bpuverify.bpu.model.early_protection import Identity, ProtectionLedger, guidance
from bpuverify.utage.model.semantic import Context, Feedback, Source
from tests.bpu.scoreboard.test_early_short_protection import Program as WindowProgram
from tests.bpu.scoreboard.test_early_positive import Program as PositiveProgram

import pytest


class Program(WindowProgram, PositiveProgram):
    def make_checks(self, pc, tag_class):
        return EarlyPositiveProtectionChecks(EarlyPositiveProtectionCoverage(), self.mode, pc)

    def base_bias(self, source, taken):
        checks = self.checks
        before = resident(self.model.sources, checks.identity.key), checks.ledger.protection
        if not taken:
            source = self.steer(source, 0)
        self.enable(True)
        for _ in range(128):
            token = self.step().metadata
            if (token is not None and main_counter(token) == (3 if taken else 0)
                    and steady_history(token, 2 if taken else 4)
                    and (owner := ahead_owner(self.model.sources, token)) is not None
                    and owner[1] == (3 if taken else 0)):
                source = self.receipt(token); self.quiet()
                checks.preserved_base_bias(source, before, taken)
                return source
        raise AssertionError('normal other-history base bias did not complete')

    def original_taken(self, source, *, older=None, longer=False, mutate=None, expect_taken=None):
        if older is not None:
            self.enable(False)
            for position in older:
                self.recovery_position = position
                source = self.query(source)
            self.recovery_position = 4
        self.enable(True)
        return self.bounded_source(source, longer=longer, mutate=mutate, expect_taken=expect_taken)

    def seed(self):
        source = self.prepared_positive()
        self.checks.arm_seed()
        source = self.base_bias(source, True)
        if self.mode != 'direction-return':
            for _ in range(3):
                source = self.original_taken(source)
        return source

    def complete(self):
        source = self.seed(); checks = self.checks
        if self.mode in ('upper-hold', 'upper-release'):
            for edge in ('approach-upper', 'reach-upper', 'upper-hold'):
                source = self.base_bias(source, False)
                source = self.steer(source, 3); self.enable(True)
                source = self.original_taken(source)
                assert edge in checks.confirmed
            if self.mode == 'upper-release':
                source = self.steer(source, 0)
                source = self.original_taken(source, older=OLDER_PATHS[1])
                assert 'upper-release' in checks.confirmed
        elif self.mode == 'lower-recover':
            source = self.steer(source, 0)
            for path, edge in zip(OLDER_PATHS, ('reach-lower', 'lower-hold'), strict=True):
                source = self.original_taken(source, older=path)
                assert edge in checks.confirmed
            source = self.steer(source, 3); self.enable(True)
            source = self.original_taken(source)
            assert 'lower-recover' in checks.confirmed
        else:
            source = self.steer(source, 0)
            source = self.original_taken(source, older=OLDER_PATHS[0])
            assert 'T-becomes-NT' in checks.confirmed
            source = self.steer(source, 3)
            source = self.original_taken(source, expect_taken=False)
            assert 'NT-error-restores-T' in checks.confirmed
            source = self.base_bias(source, False)
            source = self.steer(source, 3)
            source = self.original_taken(source)
            assert 'T-correction-restores-protection' in checks.confirmed
        if self.mode in ('upper-release', 'lower-recover'):
            source = self.steer(source, 0)
            source = self.original_taken(source, older=OLDER_PATHS[1], longer=True)
        source = self.steer(source, 3); self.enable(True)
        source = self.original_taken(source)
        checks.fresh_consumer(source); self.quiet()
        return source


@pytest.mark.parametrize('mode', tuple(EDGES))
async def test_predeclared_taken_record_limits_and_reverse_have_independent_actual_confirmations(mode):
    program = Program(mode); source = program.complete(); checks = program.checks
    assert checks.identity.table == 0 and provider(program.model.sources, source.token).counter >= 4
    assert [(event.counter_before, event.counter_after, event.before, event.after)
            for event, _, _ in checks.neutral_confirmations] == (
                [] if mode == 'direction-return' else [(4,5,1,1), (5,6,1,1), (6,7,1,1)])
    assert set(checks.confirmed) == {edge[0] for edge in EDGES[mode]}
    assert checks.boundaries.groups['checked'].coverage == 0
    checks.finish_boundaries(program.named)
    assert checks.boundaries.groups['checked'].coverage == pytest.approx(
        100*len(rules(mode))/sum(len(rules(m)) for m in EDGES))


@pytest.mark.parametrize('fault', ('no-preparation', 'no-short-seed', 'two-short-seeds',
                                 'unconfirmed-seed', 'wrong-direction-strength', 'wrong-protection'))
async def test_t_seed_is_declared_from_confirmed_normal_learning_before_driving(fault):
    program = Program('upper-hold'); program.prepared_positive(); checks = program.checks
    key = next(key for key in checks.protected_positive if key[0] == 0)
    seed, entry, useful = checks.protected_positive[key]
    if fault == 'no-preparation':
        checks.positive_prepared = None
    elif fault == 'no-short-seed':
        del checks.protected_positive[key]
    elif fault == 'two-short-seeds':
        checks.protected_positive[(0, key[1]+1)] = seed, entry, useful
    elif fault == 'unconfirmed-seed':
        checks.protected_positive[key] = replace(seed, compared=None), entry, useful
    elif fault == 'wrong-direction-strength':
        checks.protected_positive[key] = seed, replace(entry, counter=5), useful
    else:
        checks.protected_positive[key] = seed, entry, 2
    with pytest.raises(AssertionError):
        checks.arm_seed()
    assert checks.identity is None and checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('changed', ('target', 'unrelated'))
async def test_neutral_guidance_actual_protection_must_hold_before_strength_credit(changed):
    program = Program('upper-hold'); source = program.prepared_positive(); checks = program.checks
    checks.arm_seed(); source = program.base_bias(source, True); before = []
    def corrupt(actual):
        if checks.pending is None or checks.pending[1].kind != 'neutral':
            return
        before.append((program.model.sources.short.state(), checks.ledger.counter, checks.ledger.protection))
        table, index = checks.identity.key if changed == 'target' else (1, 511)
        values = [list(row) for row in actual['useful']]; values[table][index] ^= 1
        actual['useful'] = tuple(tuple(row) for row in values)
    with pytest.raises(AssertionError):
        program.original_taken(source, mutate=corrupt)
    assert len(before) == 1
    assert before[0] == (program.model.sources.short.state(), checks.ledger.counter, checks.ledger.protection)
    assert not checks.neutral_confirmations and not checks.confirmed
    assert checks.boundaries.groups['checked'].coverage == 0


async def test_consistent_t_sources_strengthen_direction_but_cannot_claim_any_reward_boundary():
    program = Program('upper-hold'); source = program.seed(); checks = program.checks
    assert (checks.ledger.counter, checks.ledger.protection) == (7, 1)
    assert len(checks.neutral_confirmations) == 3 and not checks.confirmed
    source = program.original_taken(source)
    assert provider(program.model.sources, source.token).base
    assert (checks.ledger.counter, checks.ledger.protection) == (7, 1)
    assert len(checks.neutral_confirmations) == 3 and not checks.confirmed
    assert checks.boundaries.groups['checked'].coverage == 0


async def test_t_error_must_allocate_nt_not_a_new_t_record_even_when_original_t_remains():
    program = Program('lower-recover'); source = program.seed(); checks = program.checks
    source = program.steer(source, 0)
    for path in OLDER_PATHS:
        source = program.original_taken(source, older=path)
    assert checks.parallel_confirmed
    step = program.step; corrupted = []
    def corrupt(actual):
        if not checks.window_active or not checks.longer_window:
            return
        for entry in actual['meta']['entries']:
            if entry['valid'] and entry['hit'] and entry['provider'] == 1 and entry['counter'] == 3:
                entry['counter'] = 4; corrupted.append(program.tick)
    def wrong_nt(event=None, **kwargs):
        kwargs['mutate'] = corrupt
        return step(event, **kwargs)
    program.step = wrong_nt
    with pytest.raises(AssertionError):
        program.original_taken(source, older=OLDER_PATHS[1], longer=True)
    assert len(corrupted) == 1 and 'fresh-long-consumer' not in checks.completed
    assert checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-neutral-proof', 'missing-long-consumer', 'old-seed-rebased'))
async def test_incomplete_t_boundary_or_rebased_seed_cannot_close(fault):
    program = Program('lower-recover'); program.complete(); checks = program.checks
    if fault == 'missing-neutral-proof':
        checks.neutral_confirmations.clear()
    elif fault == 'missing-long-consumer':
        checks.completed.discard('fresh-long-consumer')
    else:
        seed = checks.original_seed
        checks.original_seed = replace(seed, snapshot=replace(seed.snapshot, end_position=15))
    with pytest.raises(AssertionError):
        checks.finish_boundaries(program.named)
    assert checks.boundaries.groups['checked'].coverage == 0


def test_direction_flip_cannot_be_skipped_or_relabelled_as_a_t_recovery_reward():
    identity = Identity(0, 0, 0, 2); ledger = ProtectionLedger(counter=4, protection=0)
    def feedback(counter, predicted, base, actual):
        return Feedback(0x40000000, Context(), (0, 0),
            (Source(True, 2, True, 0, counter, predicted, base),), 2, actual, 1)
    events = []
    for owner, f in enumerate((feedback(4, True, True, False), feedback(3, False, False, True),
                               feedback(4, True, False, True))):
        events.append(ledger.apply(owner, *guidance(f, identity)))
    assert [(e.kind, e.counter_before, e.counter_after, e.before, e.after) for e in events] == [
        ('penalty',4,3,0,0), ('penalty',3,4,0,0), ('reward',4,5,0,1)]


@pytest.mark.parametrize('fault', ('wrong-crossing-strength', 'restoration-mislabelled-reward', 'missing-NT-error'))
async def test_direction_return_needs_both_errors_before_the_real_t_reward(fault):
    program = Program('direction-return'); program.complete(); checks = program.checks
    name = 'T-becomes-NT' if fault == 'wrong-crossing-strength' else 'NT-error-restores-T'
    event, written, actual = checks.confirmed[name]
    if fault == 'missing-NT-error':
        del checks.confirmed[name]
    else:
        event = replace(event, counter_before=5) if fault == 'wrong-crossing-strength' else replace(event, kind='reward')
        checks.confirmed[name] = event, written, actual
    with pytest.raises(AssertionError):
        checks.finish_boundaries(program.named)
    assert checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('value', (0, 1, 'taken'))
async def test_window_polarity_is_declared_before_opening_not_inferred_or_coerced(value):
    program = Program('direction-return'); program.prepared_positive(); checks = program.checks
    checks.arm_seed()
    with pytest.raises(AssertionError):
        checks.open_original(expect_taken=value)
    assert not checks.window_active and checks.acceptance is None


async def test_allocated_direction_cannot_be_overridden_by_the_consumer_request():
    program = Program('direction-return'); program.prepared_positive(); checks = program.checks
    checks.arm_seed()
    with pytest.raises(AssertionError, match='original S3 guidance'):
        checks.open_original(longer=True, expect_taken=False)
    assert not checks.window_active and checks.acceptance is None


def test_semantic_case_has_no_edges_raw_pin_writes_or_task_join_details():
    tree = ast.parse(Path('bpuverify/bpu/case/early_positive_protection.py').read_text())
    forbidden = {'ClockCycles','RisingEdge','FallingEdge','gather','create_task','set_','get_'}
    assert not {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} & forbidden
    assert not {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} & forbidden
