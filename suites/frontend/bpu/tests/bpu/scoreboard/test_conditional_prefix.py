"""Synthetic actuals test rejection paths; never DUT or hardware coverage credit."""
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard, XEvent, XEventKind, XPhase
from tests.bpu.scoreboard._conditional_prefix_program import Program as ReferenceProgram
from bpuverify.bpu.model.conditional_prefix import PROFILES, target_state
from bpuverify.bpu.coverage.conditional_prefix import Coverage, RULES
from bpuverify.bpu.checker.conditional_prefix import Checks


def actual_guard():
    return dict(reset=0, region_write=0, regions=[dict(valid=0, region=0) for _ in range(16)],
        updates=[0] * 3, incoming=[0] * 6, maintenance=[0] * 6,
        write_valid=[0] * 6, write_ready=[1] * 6, reads=[1] * 6)


class Program(ReferenceProgram):
    def __init__(self, profile):
        super().__init__(profile)
        self.checks = Checks(profile)
        self.receipts = {}
        self.mutate_actual = None
        self.checks.pipeline = NS(model=self.model, board=Scoreboard('synthetic-prefix-qualification'),
            source_token=lambda source: source.token, raise_failure=lambda: None, last_tick=None)

    def receipt(self, token): return self.receipts[token.sequence]

    def step(self, event=None):
        event = self.event if event is None else event
        c = self.checks
        if event.feedback is not None:
            request = event.feedback
            guarded = c.guard is not None and c.winner is request.origin
            c.plan('guarded-conditional-only' if guarded else f'real-outcome-{len(c.plans)}',
                self.receipt(request.origin), tuple(b for b in request.branches if b is not None))
        cycle = self.model.evaluate(event)
        self.tick += 2
        actual_event = XEvent(event_id=self.tick, tick=self.tick, phase=XPhase.RISING_STABLE, kind=XEventKind.CLOCK_RISE)
        c.pipeline.current_event = actual_event
        c.candidates(dict(observed={}), event, cycle, self.model, 'synthetic', None)
        self.model.advance(event)
        if self.guard_state is not None:
            assert target_state(self.model.sources) == self.guard_state
            self.guard_cycles += 1
        c.checked(self.tick)
        value = actual_guard()
        if self.mutate_actual is not None and c.guard is not None: self.mutate_actual(value)
        c.actual(actual_event, value)
        c.pipeline.last_tick = self.tick
        if cycle.metadata is not None and event.redirect is None:
            token = cycle.metadata
            self.receipts[token.sequence] = NS(token=token, meta_tick=self.tick, meta=dict(owner=token.sequence))
        if cycle.final_repair: self.repairs.append((self.tick, cycle))
        return cycle

    def prepare_sources(self):
        result = super().prepare_sources()
        c = self.checks
        c.seed = self.receipt(self.seed)
        c.stable = self.receipt(self.anchor)
        c.target_control = self.receipt(self.model.published[result['target_original']])
        for source in (c.seed, c.stable, c.target_control): c.save(source)
        return result

    def configure(self, **values):
        super().configure(**values)
        if values.get('early') is True: self.checks.open()

    def conditional(self, source, **values):
        guarded = self.checks.guard is not None and self.checks.winner is source
        result = super().conditional(source, **values)
        if guarded:
            self.checks.save(self.receipt(source))
            self.checks.close_guard()
        return result

    def completed(self):
        result = super().complete()
        return self.receipt(self.model.published[result['fresh_indirect_consumer']['owner']])


@pytest.mark.parametrize('profile', PROFILES)
async def test_pure_program_has_complete_atomic_conditional_prefix_witnesses(profile):
    p = Program(profile)
    fresh = p.completed()
    c = p.checks
    assert c.coverage.groups['checked'].coverage == 0
    value = c.finish(fresh)
    assert value['atomic_lifetime_closed'] and c.closed
    assert set(c.reached_rules) == set(RULES)
    assert c.coverage.groups['checked'].coverage == 100 / len(PROFILES)


FAULTS = ('teacher', 'selected', 'winner', 'middle-witness', 'final-witness', 'guard-witness',
    'missing-teacher-receipt', 'copied-teacher-token', 'middle-report', 'final-report',
    'acceptance', 'guard-cycles', 'actual-ticks', 'original-public-metadata')


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('fault', FAULTS)
async def test_missing_or_rebound_completion_evidence_latches_failure_without_credit(profile, fault):
    p = Program(profile)
    fresh = p.completed()
    c = p.checks
    if fault in ('teacher', 'selected', 'winner'): setattr(c, fault, None)
    elif fault in ('middle-witness', 'final-witness', 'guard-witness'): setattr(c, '_' + fault.replace('-', '_'), None)
    elif fault == 'missing-teacher-receipt': c.saved.pop(c.teacher.meta_tick)
    elif fault == 'copied-teacher-token':
        from dataclasses import replace
        c.teacher.token = replace(c.teacher.token)
    elif fault == 'middle-report': c.middle['owner'] += 1
    elif fault == 'final-report': c.final['target'] += 1
    elif fault == 'acceptance': c.acceptance = None
    elif fault == 'guard-cycles': c.actual_guard_cycles -= 1
    elif fault == 'actual-ticks': c.actual_ticks.pop()
    elif fault == 'original-public-metadata': c.teacher.meta['changed'] = True
    with pytest.raises(AssertionError) as first: c.finish(fresh)
    with pytest.raises(AssertionError) as second: c.finish(fresh)
    assert first.value is second.value and c.failure is first.value
    assert not c.closed and not c.coverage.closed and c.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('fault', ('target-update', 'buffer-insertion', 'actual-service', 'region-write', 'region-content', 'maintenance'))
async def test_any_actual_unexecuted_target_learning_or_state_change_fails_before_credit(profile, fault):
    p = Program(profile)
    def mutate(value):
        if fault == 'target-update': value['updates'][2] = 1
        elif fault == 'buffer-insertion': value['incoming'][5] = 1
        elif fault == 'actual-service': value['write_valid'][5] = 1
        elif fault == 'region-write': value['region_write'] = 1
        elif fault == 'region-content': value['regions'][15] = dict(valid=1, region=1)
        else: value['maintenance'][5] = 1
    p.mutate_actual = mutate
    with pytest.raises(AssertionError): p.completed()
    assert p.checks.failure is not None and p.checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('rule', RULES)
def test_omitting_one_semantic_obligation_never_grants_partial_checked_credit(rule):
    c = Coverage(PROFILES[0])
    for item in RULES:
        if item != rule:
            c.record('reached', item, 10)
            c.record('checked', item, 12)
    with pytest.raises(AssertionError): c.finish()
    assert c.groups['checked'].coverage == 0 and not c.closed
