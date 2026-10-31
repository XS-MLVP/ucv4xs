"""Synthetic actuals qualify checkers, never DUT or functional-point coverage."""
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from toffee import Scoreboard, XEvent, XEventKind, XPhase

from tests.bpu.scoreboard._indirect_path_program import Program as ReferenceProgram
from suites.frontend.bpu.bpu.checker.indirect_path_ownership import Checks
from suites.frontend.bpu.bpu.model.indirect_path_ownership import PROFILES, RULES
from suites.frontend.bpu.bpu.model.indirect_path_ownership import PHASES
from suites.frontend.bpu.bpu.checker.early_direction import live_values, fast_values
from suites.frontend.bpu.tage.model.semantic import HISTORIES
from tests.bpu.scoreboard.test_early_direction_checking import actual_live, actual_fast


class Program(ReferenceProgram):
    def __init__(self, profile):
        entry, mode = profile.split('.')
        super().__init__(0x40000001 if entry == 'compressed-entry' else 0x40000002,
            flowing=mode == 'flowing')
        self.checks = Checks(profile)
        self.receipts = {}
        self.s1_accepts = {}
        self.notification_phase = XPhase.RISING_STABLE
        self.mutate = None
        self.checks.pipeline = NS(model=self.model, board=Scoreboard('candidate-pure-lifetime'),
            raise_failure=lambda: None, source_token=lambda source: source.token)

    def step(self, event=None):
        event = self.event if event is None else event
        cycle = self.model.evaluate(event)
        self.tick += 2
        self.checks.pipeline.current_event = XEvent(event_id=self.tick, tick=self.tick,
            phase=self.notification_phase, kind=XEventKind.CLOCK_RISE)
        actual = actual_live(self.model.sources, cycle.enabled[1])
        if self.mutate is not None:
            self.mutate(actual)
        self.checks.candidates(dict(observed=dict(early_direction=actual)), event, cycle, self.model, 'synthetic', None)
        expected, observed = live_values(self.model.sources, cycle.enabled[1], actual)
        self.checks.pipeline.board.check(expected=expected, actual=observed)
        expected, observed = fast_values(self.model.sources, cycle, actual_fast(self.model.sources, cycle))
        self.checks.pipeline.board.check(expected=expected, actual=observed)
        self.model.advance(event)
        self.checks.checked(self.tick)
        if cycle.fires[1] and not cycle.flushes[0]:
            self.s1_accepts[cycle.tokens[0].sequence] = self.tick
        if cycle.metadata is not None and event.redirect is None:
            token = cycle.metadata
            self.receipts[token.sequence] = NS(token=token, prediction_tick=self.s1_accepts[token.sequence],
                meta_tick=self.tick, meta=dict(owner=token.sequence))
        if cycle.final_repair:
            self.repairs.append((self.tick, cycle))
        return cycle

    def receipt(self, token):
        return self.receipts[token.sequence]

    def resolve(self, source, *args, **kwargs):
        self.checks.plan_resolution(PHASES[len(self.feedbacks)], self.receipt(source))
        return super().resolve(source, *args, **kwargs)

    def warm(self):
        token = super().warm()
        self.checks.early_consumer(self.receipt(token))
        return token

    def source(self, predicate=lambda _: True, *, pc=None):
        token = super().source(predicate, pc=pc)
        if (self.checks.stable is None and len(self.feedbacks) == 5 and token.pc == self.a
                and token.history.history % (1 << max(HISTORIES)) == self.checks.program.stable_predecessor_history):
            self.checks.stable_predecessor(self.receipt(token))
        return token

    def controls(self, *, early=None, target=None):
        if target is False:
            self.checks.target_consumer(self.receipt(self.originals[-1]))
        super().controls(early=early, target=target)
        if early is True and len(self.feedbacks) == len(PHASES):
            self.checks.open()

    async def complete(self):
        detail = self.prepare()
        self.checks.save(self.receipt(self.model.published[detail['owner']]))
        for _ in range(256):
            self.step()
            if self.checks.new_a is not None and self.checks.new_b is not None:
                break
        else:
            raise AssertionError('both fresh originals must publish in one continuous observation window')
        for token, _ in (self.checks._restored_witness, self.checks._consumer_witness):
            self.checks.save(self.receipt(token))
        self.quiet()


@pytest.mark.parametrize('profile', PROFILES)
async def test_atomic_closure_requires_actual_teacher_learning_and_both_new_receipts(profile):
    p = Program(profile)
    await p.complete()
    c = p.checks
    assert c.coverage.groups['checked'].coverage == 0
    c.finish()
    assert c.closed and c.coverage.closed and set(c.reached_rules) == set(RULES)
    assert c.coverage.groups['checked'].coverage == 100 / len(PROFILES)
    assert c.facts['atomic_lifetime_closed'] and c.facts['checked_obligations'] == list(RULES)


FAULTS = (
    'seed', 'stable', 'target-control', 'teacher', 'acceptance', 'selected',
    'middle-owner', 'repair-owner', 'confirmation-owner', 'confirmation-witness', 'next-state-time',
    'restored-owner', 'restored-history', 'restored-report', 'consumer-report', 'consumer-provider',
    'consumer-identity', 'missing-a-receipt', 'missing-b-receipt', 'receipt-copy', 'public-metadata',
    'ahead-snapshot', 'short-snapshot', 'tage-read', 'tage-result', 'target-read', 'target-result',
)


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('fault', FAULTS)
async def test_missing_or_rebound_semantic_evidence_latches_failure_without_checked_credit(profile, fault):
    p = Program(profile)
    await p.complete()
    c = p.checks
    if fault == 'seed':
        c.seed = None
    elif fault == 'stable':
        c.stable = None
    elif fault == 'target-control':
        c.target_control = None
    elif fault == 'teacher':
        c.teacher = None
    elif fault == 'acceptance':
        import asyncio
        c.acceptance = asyncio.get_running_loop().create_future()
    elif fault == 'selected':
        c.selected = None
    elif fault == 'middle-owner':
        c.middle['owner'] += 1
    elif fault == 'repair-owner':
        c.repair['owner'] += 1
    elif fault == 'confirmation-owner':
        c.confirmed['owner'] += 1
    elif fault == 'confirmation-witness':
        c.confirmed['tag'] ^= 1
    elif fault == 'next-state-time':
        c.confirmed['confirmed_tick'] += 2
    elif fault == 'restored-owner':
        c.repair['restored_owner'] += 1
    elif fault == 'restored-history':
        c.repair['restored_history'] ^= 1
    elif fault == 'restored-report':
        c.new_a['owner'] += 1
    elif fault == 'consumer-report':
        c.new_b['owner'] += 1
    elif fault == 'consumer-provider':
        c.new_b['provider']['counter'] ^= 1
    elif fault == 'consumer-identity':
        c.new_b['provider']['tag'] ^= 1
    elif fault.startswith('missing-'):
        token = c._restored_witness[0] if fault == 'missing-a-receipt' else c._consumer_witness[0]
        key = next(key for key, (_, owner, _, _) in c.saved.items() if owner is token)
        c.saved.pop(key)
    elif fault == 'receipt-copy':
        c.teacher.token = replace(c.teacher.token)
    elif fault == 'public-metadata':
        c.teacher.meta = dict(changed=True)
    else:
        key = c.teacher.meta_tick
        source, token, snapshots, metadata = c.saved[key]
        domain = ('ahead-snapshot', 'short-snapshot', 'tage-read', 'tage-result', 'target-read', 'target-result').index(fault)
        changed = list(snapshots)
        changed[domain] = None
        c.saved[key] = source, token, tuple(changed), metadata
    with pytest.raises(AssertionError) as first:
        c.finish()
    with pytest.raises(AssertionError) as repeated:
        c.finish()
    assert first.value is repeated.value
    assert not c.closed and not c.coverage.closed and c.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('rule', RULES)
async def test_omitting_any_human_semantic_obligation_prevents_atomic_closure(profile, rule):
    p = Program(profile)
    original = p.checks.mark
    p.checks.mark = lambda name, tick: original(name, tick) if name != rule else None
    await p.complete()
    with pytest.raises(AssertionError):
        p.checks.finish()
    assert not p.checks.coverage.closed and p.checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('table', (0, 1))
async def test_unrelated_actual_protection_corruption_fails_before_any_checked_credit(profile, table):
    p = Program(profile)
    def corrupt(actual):
        values = [list(row) for row in actual['useful']]
        values[table][400] ^= 1
        actual['useful'] = tuple(tuple(row) for row in values)
    p.mutate = corrupt
    with pytest.raises(AssertionError):
        await p.complete()
    assert p.checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('phase', (XPhase.DRIVE_STABLE, XPhase.EXTERNAL))
async def test_only_already_compared_monitor_acceptance_can_release_the_driver(profile, phase):
    p = Program(profile)
    p.notification_phase = phase
    with pytest.raises(AssertionError):
        await p.complete()
    assert p.checks.acceptance is not None and not p.checks.acceptance.done()
    assert p.checks.coverage.groups['checked'].coverage == 0
