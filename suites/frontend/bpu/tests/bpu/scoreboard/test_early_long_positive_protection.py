from suites.frontend.bpu.bpu.model.early_opposition import FALLBACK
"""Longest-provider boundary and failure accounting with synthetic actuals only."""
import ast
from dataclasses import replace
from pathlib import Path

import pytest

from suites.frontend.bpu.bpu.checker.early_long_positive_protection import EarlyLongPositiveProtectionChecks
from suites.frontend.bpu.bpu.coverage.early_long_positive_protection import EarlyLongPositiveProtectionCoverage
from suites.frontend.bpu.bpu.model.early_long_positive_protection import (EDGES, REVISIT_PREFIX, SHORT_REVISIT_PREFIX,
                                                             rules, intended_identity)
from suites.frontend.bpu.bpu.model.early_opposition import provider
from suites.frontend.bpu.bpu.model.early_protection import guidance, ProtectionLedger
from suites.frontend.bpu.bpu.model.path_history import path_contribution, SHIFT
from suites.frontend.bpu.utage.model.semantic import Context, Feedback, Source, indices, tag
from tests.bpu.scoreboard.test_early_positive_protection import Program as TakenProgram


class Program(TakenProgram):
    def make_checks(self, pc, tag_class):
        return EarlyLongPositiveProtectionChecks(EarlyLongPositiveProtectionCoverage(), self.mode, pc)

    def original_long(self, source, *, penalty=False, mutate=None, expect_taken=None):
        if penalty:
            self.enable(False)
            for position in REVISIT_PREFIX:
                self.recovery_position = position
                source = self.query(source)
            self.recovery_position = FALLBACK
        self.enable(True)
        return self.bounded_source(source, recovery_position=2 if penalty else FALLBACK,
                                   mutate=mutate, expect_taken=expect_taken)

    def companion_short(self, source, *, preserve=False, mutate=None):
        self.enable(False)
        for position in SHORT_REVISIT_PREFIX:
            self.recovery_position = position
            source = self.query(source)
        self.recovery_position = FALLBACK
        self.enable(True)
        return self.bounded_source(source, mutate=mutate,
                                   open_window=lambda: self.checks.open_short(preserve=preserve))

    def error_ready(self):
        return self.error_ready_from(self.seed())

    def complete(self):
        source = self.seed(); checks = self.checks
        if self.mode in ('upper-hold', 'upper-release'):
            for edge in ('reach-upper', 'upper-hold'):
                source = self.base_bias(source, False)
                source = self.steer(source, 3)
                source = self.original_long(source)
                assert edge in checks.confirmed
            if self.mode == 'upper-release':
                source = self.steer(source, 0)
                source = self.original_long(source, penalty=True)
                assert 'upper-release' in checks.confirmed
        elif self.mode == 'lower-recover':
            source = self.steer(source, 0)
            source = self.companion_short(source)
            for edge in ('toward-lower', 'reach-lower', 'lower-hold'):
                source = self.original_long(source, penalty=True)
                assert edge in checks.confirmed
            source = self.steer(source, 3)
            source = self.companion_short(source, preserve=True)
            source = self.original_long(source)
            assert 'lower-recover' in checks.confirmed
        else:
            source = self.error_ready_from(source)
            for edge in ('toward-lower', 'reach-lower', 'lower-hold', 'T-becomes-NT'):
                source = self.original_long(source, penalty=True)
                assert edge in checks.confirmed
            source = self.steer(source, 3)
            source = self.original_long(source, penalty=True, expect_taken=False)
            assert 'NT-error-restores-T' in checks.confirmed
            source = self.companion_short(source, preserve=True)
            source = self.base_bias(source, False)
            source = self.steer(source, 3)
            source = self.original_long(source)
            assert 'T-correction-restores-protection' in checks.confirmed
        source = self.steer(source, 3)
        source = self.original_long(source)
        checks.fresh_consumer(source); self.quiet()
        return source

    def error_ready_from(self, source):
        return self.companion_short(self.steer(source, 0))


@pytest.mark.parametrize('mode', tuple(EDGES))
async def test_original_long_t_record_limits_and_no_longer_candidate_are_independently_confirmed(mode):
    program = Program(mode); source = program.complete(); checks = program.checks
    assert checks.identity == intended_identity(program.pc)
    assert provider(program.model.sources, source.token).table == 1
    assert [(event.counter_before, event.counter_after, event.before, event.after)
            for event, _, _ in checks.neutral_confirmations] == [(4,5,2,2), (5,6,2,2), (6,7,2,2)]
    assert set(checks.confirmed) == {edge[0] for edge in EDGES[mode]}
    assert len(checks.confirmed_failures) == sum(edge[1] == 'penalty' for edge in EDGES[mode])
    assert not checks.parallel_confirmed and checks.failure_pending is None
    assert checks.boundaries.groups['checked'].coverage == 0
    checks.finish_boundaries(program.named)
    assert checks.boundaries.groups['checked'].coverage == pytest.approx(
        100*len(rules(mode))/sum(len(rules(m)) for m in EDGES))
    if mode == 'lower-recover':
        assert [row['common_read_protection'] for row in checks.available_errors] == [(0,2),(0,1),(0,0)]
        assert checks.short_release['owner'] not in {row[0] for row in checks.confirmed_failures}
        assert (checks.short_consumer['counter'], checks.short_consumer['protection']) == (6,0)
    if mode == 'direction-crossing':
        assert [row['common_read_protection'] for row in checks.available_errors] == [(0,2),(0,1),(0,0),(0,0),(0,0)]
        origins = checks.boundaries.groups['checked'].report()['points'][0]['provenance'][mode+'.restored-T-before-protection']
        restored = next(iter(origins.values()))['first']
        assert restored['previous_error_confirmation'] < restored['prediction_tick']
        assert restored['owner'] == restored['subsequent_reward_owner']
        assert (restored['counter'],restored['protection']) == (4,0)
    if mode != 'upper-hold':
        point = checks.boundaries.groups['checked'].report()['points'][0]
        origins = point['provenance'][mode+'.last-provider-error-accounted']
        witness = next(iter(origins.values()))['first']
        assert [row['owner'] for row in witness['confirmed_failures']] == [row[0] for row in checks.confirmed_failures]
        assert all(row['failure_after'] == row['failure_before']+1
                   and row['written_tick']+2 == row['actual_confirmation_tick']
                   for row in witness['confirmed_failures'])


@pytest.mark.parametrize('fault', ('arbitrary-long', 'wrong-read-index', 'wrong-match-tag',
                                 'short-protection-initial', 'wrong-counter', 'unconfirmed-seed'))
async def test_long_seed_cannot_be_an_arbitrary_hit_or_use_short_table_initial_state(fault):
    program = Program('upper-hold'); program.prepared_positive(); checks = program.checks
    identity = intended_identity(program.pc); key = identity.key
    seed, entry, useful = checks.protected_positive[key]
    if fault == 'arbitrary-long':
        del checks.protected_positive[key]
    elif fault == 'wrong-read-index':
        del checks.protected_positive[key]
        checks.protected_positive[(1, key[1]^1)] = seed, entry, useful
    elif fault == 'wrong-match-tag':
        checks.protected_positive[key] = seed, replace(entry, tag=entry.tag^1), useful
    elif fault == 'short-protection-initial':
        checks.protected_positive[key] = seed, entry, 1
    elif fault == 'wrong-counter':
        checks.protected_positive[key] = seed, replace(entry, counter=5), useful
    else:
        checks.protected_positive[key] = replace(seed, compared=None), entry, useful
    with pytest.raises(AssertionError):
        checks.arm_seed()
    assert checks.identity is None and checks.boundaries.groups['checked'].coverage == 0


async def test_failures_during_normal_preparation_are_not_discarded_at_the_target_scope():
    program = Program('lower-recover'); source = program.seed(); checks = program.checks
    assert checks.failure_ledger.count > 0 and not checks.confirmed_failures
    checks.failure_ledger.count = 0  # Deliberately broken oracle: count only target errors.
    with pytest.raises(AssertionError, match='including preparation'):
        program.quiet()
    assert checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('failure-count', 'target-protection', 'unrelated-protection'))
async def test_last_provider_failure_needs_the_next_complete_actual_comparison(fault):
    program = Program('lower-recover'); source = program.error_ready(); checks = program.checks
    before = []
    def corrupt(actual):
        if checks.failure_pending is None:
            return
        before.append((program.model.sources.short.state(), checks.failure_ledger.count, checks.ledger.protection))
        if fault == 'failure-count':
            actual['maintenance']['low'] ^= 1
        else:
            table, index = checks.identity.key if fault == 'target-protection' else (0, 511)
            rows = [list(row) for row in actual['useful']]; rows[table][index] ^= 1
            actual['useful'] = tuple(tuple(row) for row in rows)
    with pytest.raises(AssertionError):
        program.original_long(source, penalty=True, mutate=corrupt)
    assert len(before) == 1 and before[0] == (
        program.model.sources.short.state(), checks.failure_ledger.count, checks.ledger.protection)
    assert not checks.confirmed_failures and checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('short-allocation', 'long-allocation', 'allocation-mask',
                                 'missing-long-update', 'unrelated-short-update'))
async def test_last_provider_error_never_allocates_backward_or_loses_its_update(fault):
    program = Program('lower-recover'); source = program.error_ready(); checks = program.checks
    corrupted = []
    def corrupt(actual):
        learning = program.model.sources.short.learning
        if learning is None or guidance(learning.feedback, checks.identity) != (False, 'penalty'):
            return
        corrupted.append(program.tick); control = actual['maintenance']
        if fault == 'allocation-mask':
            control['mask'] = 1
        else:
            table, field = {'short-allocation': (0,'allocate'), 'long-allocation': (1,'allocate'),
                            'missing-long-update': (1,'update'), 'unrelated-short-update': (0,'update')}[fault]
            control['tables'][table][field] ^= 1
    with pytest.raises(AssertionError):
        program.original_long(source, penalty=True, mutate=corrupt)
    assert len(corrupted) == 1 and not checks.confirmed_failures
    assert checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('different-owner', 'duplicate-owner', 'unconfirmed-failure'))
async def test_failure_count_alone_cannot_replace_exact_original_owner_confirmation(fault):
    program = Program('lower-recover'); program.complete(); checks = program.checks
    owner, written, actual, before, after = checks.confirmed_failures[0]
    if fault == 'different-owner':
        checks.confirmed_failures[0] = owner+10000, written, actual, before, after
    elif fault == 'duplicate-owner':
        second = checks.confirmed_failures[1]
        checks.confirmed_failures[1] = (owner, *second[1:])
    else:
        checks.failure_pending = ('not-actually-compared',)
    with pytest.raises(AssertionError):
        checks.finish_boundaries(program.named)
    assert checks.boundaries.groups['checked'].coverage == 0


async def test_a_long_t_consumer_must_still_match_the_declared_original_identity():
    program = Program('upper-hold'); source = program.complete(); checks = program.checks
    checks.identity = replace(checks.identity, index=checks.identity.index^1)
    with pytest.raises(AssertionError):
        checks.fresh_consumer(source)
    assert checks.boundaries.groups['checked'].coverage == 0


def test_read_and_match_ancestors_are_not_interchangeable_or_seeded_from_actual_signals():
    pc = 0x40000000; word = 0
    for position in REVISIT_PREFIX:
        word = (word << SHIFT) ^ path_contribution(pc+position, pc)
    read = Context.from_recent(word)
    match = Context.from_recent((word << SHIFT) ^ path_contribution(pc+2, pc))
    identity = intended_identity(pc)
    assert identity.index == indices(pc, read)[1] != indices(pc, match)[1]
    assert identity.tag == tag(pc, match, 1) != tag(pc, read, 1)
    tree = ast.parse(Path('bpu/model/early_long_positive_protection.py').read_text())
    assert not any(isinstance(n, ast.ImportFrom) and n.module and
                   any(part in n.module.split('.') for part in ('driver','bundle','monitor','toffee'))
                   for n in ast.walk(tree))


def test_long_record_case_exposes_no_edges_raw_io_or_async_task_join():
    tree = ast.parse(Path('bpu/case/early_long_positive_protection.py').read_text())
    forbidden = {'ClockCycles','RisingEdge','FallingEdge','gather','create_task','set_','get_'}
    assert not {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} & forbidden
    assert not {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} & forbidden


def test_long_nt_error_restores_direction_without_protection_reward():
    pc = 0x40000000; context = Context(); identity = replace(intended_identity(pc), index=indices(pc,context)[1], tag=tag(pc,context,1))
    ledger = ProtectionLedger(counter=3, protection=0)
    nt = Feedback(pc,context,indices(pc,context), (Source(True,2,True,1,3,False,False),), 2,True,1)
    t = replace(nt, sources=(Source(True,2,True,1,4,True,False),))
    assert guidance(nt,identity) == (True,'penalty')
    assert guidance(t,identity) == (True,'reward')
    events = [ledger.apply(1,*guidance(nt,identity)),ledger.apply(2,*guidance(t,identity))]
    assert [(e.counter_before,e.counter_after,e.before,e.after) for e in events] == [(3,4,0,0),(4,5,0,1)]


@pytest.mark.parametrize('fault', ('missing-T-crossing','missing-NT-error','early-protection',
                                 'NT-error-as-reward','wrong-crossing-counter','no-restored-consumer',
                                 'wrong-restored-owner','early-consumer','wrong-history'))
async def test_direction_crossing_needs_every_semantic_step_and_its_fresh_restored_owner(fault):
    program = Program('direction-crossing'); program.complete(); checks = program.checks
    if fault.startswith('missing-'):
        del checks.confirmed['T-becomes-NT' if fault=='missing-T-crossing' else 'NT-error-restores-T']
    elif fault in ('early-protection','NT-error-as-reward','wrong-crossing-counter'):
        name = 'T-becomes-NT' if fault=='wrong-crossing-counter' else 'NT-error-restores-T'
        event,written,actual = checks.confirmed[name]
        event = replace(event, **({'after':1} if fault=='early-protection' else
                                 {'kind':'reward'} if fault=='NT-error-as-reward' else {'counter_after':4}))
        checks.confirmed[name] = event,written,actual
    elif fault=='no-restored-consumer':
        checks.restored_taken = None
    else:
        token,prediction = checks.restored_taken
        if fault=='wrong-restored-owner':
            token = replace(token,sequence=token.sequence+10000)
        elif fault=='early-consumer':
            prediction = checks.confirmed['NT-error-restores-T'][2]
        else:
            token = replace(token,history=checks.original_seed.owner.history)
        checks.restored_taken = token,prediction
    with pytest.raises(AssertionError):
        checks.finish_boundaries(program.named)
    assert checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('restoration-reward','NT-source-counter'))
async def test_actual_nt_error_cannot_silently_restore_protection_or_change_its_original_direction(fault):
    program = Program('direction-crossing'); source = program.error_ready(); checks = program.checks
    for _ in range(4):
        source = program.original_long(source,penalty=True)
    source = program.steer(source,3); damaged = []
    def corrupt(actual):
        if not checks.window_active or checks.window_taken:
            return
        if fault=='restoration-reward':
            if checks.failure_pending is None or checks.ledger.counter!=4:
                return
            values = [list(row) for row in actual['useful']]
            values[1][checks.identity.index] = 1
            actual['useful'] = tuple(tuple(row) for row in values)
        else:
            entry = next((e for e in actual['meta']['entries'] if e['valid'] and e['hit']
                          and e['provider']==1 and e['counter']==3),None)
            if entry is None:
                return
            entry['counter'] = 4
        damaged.append(program.model.sources.short.state())
    step = program.step
    def sample_original_nt(event=None, **kwargs):
        kwargs['mutate'] = corrupt
        return step(event, **kwargs)
    program.step = sample_original_nt
    with pytest.raises(AssertionError):
        program.original_long(source,penalty=True,expect_taken=False)
    assert len(damaged)==1 and damaged[0]==program.model.sources.short.state()
    assert checks.boundaries.groups['checked'].coverage == 0


async def test_no_backward_allocation_requires_actual_short_availability_not_just_no_commands():
    program = Program('lower-recover'); source = program.steer(program.seed(), 0)
    with pytest.raises(AssertionError, match='actually released first'):
        program.original_long(source, penalty=True)
    assert not program.checks.available_errors and not program.checks.confirmed_failures
    assert program.checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-release', 'wrong-release-owner', 'wrong-read-protection',
                                 'wrong-read-index', 'wrong-confirmation', 'duplicate-owner',
                                 'missing-consumer', 'wrong-consumer-owner', 'wrong-consumer-state'))
async def test_free_short_and_preserved_consumer_are_required_exactly_before_checked_credit(fault):
    program = Program('lower-recover'); program.complete(); checks = program.checks
    if fault == 'missing-release':
        checks.short_release = None
    elif fault == 'wrong-release-owner':
        checks.short_release['owner'] += 10000
    elif fault == 'wrong-read-protection':
        checks.available_errors[0]['common_read_protection'] = (1,2)
    elif fault == 'wrong-read-index':
        checks.available_errors[0]['learning_indices'] = (checks.available_errors[0]['learning_indices'][0] ^ 1, checks.identity.index)
    elif fault == 'wrong-confirmation':
        checks.available_errors[0]['actual_confirmation_tick'] += 2
    elif fault == 'duplicate-owner':
        checks.available_errors[1]['owner'] = checks.available_errors[0]['owner']
    elif fault == 'missing-consumer':
        checks.short_consumer = None
    elif fault == 'wrong-consumer-owner':
        checks.short_consumer['owner'] += 10000
    else:
        checks.short_consumer['counter'] = 7
    with pytest.raises(AssertionError):
        checks.finish_boundaries(program.named)
    assert checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('counter', 'protection'))
async def test_unused_short_resident_corruption_is_detected_during_long_error_confirmation(fault):
    program = Program('lower-recover'); source = program.error_ready(); checks = program.checks
    damaged = []
    def corrupt(actual):
        if checks.failure_pending is None:
            return
        if fault == 'protection':
            values = [list(row) for row in actual['useful']]
            values[0][checks.short_identity.index] = 1
            actual['useful'] = tuple(tuple(row) for row in values)
        else:
            # Deliberately damage the semantic resident without adjusting its
            # independently owned ledger. Correct long protection is not enough.
            short = program.model.sources.short
            version = short.updates[0].newest(checks.short_identity.index)
            short.updates[0].recent = [replace(row, entry=replace(row.entry, counter=3))
                if row is version else row for row in short.updates[0].recent]
        damaged.append(program.tick)
    with pytest.raises(AssertionError):
        program.original_long(source, penalty=True, mutate=corrupt)
    assert len(damaged) == 1 and checks.boundaries.groups['checked'].coverage == 0
