"""Synthetic actual data tests checking logic, never contributes DUT coverage."""
import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard,XEvent,XPhase,XEventKind
from suites.frontend.bpu.bpu.checker.late_correction_learning import Checks,PHASES
from suites.frontend.bpu.bpu.checker.early_direction import live_values,fast_values
from suites.frontend.bpu.bpu.coverage.late_correction_learning import Coverage
from suites.frontend.bpu.bpu.model.late_correction_learning import PROFILES,RULES,program
from suites.frontend.bpu.bpu.model.early_opposition import provider
from tests.bpu.scoreboard.test_early_late_sources import Program as Foundation
from tests.bpu.scoreboard.test_early_direction_checking import actual_live,actual_fast


class Program(Foundation):
    def __init__(self,profile):
        self.profile=program(profile)
        super().__init__(self.profile.b)
        self.checks=Checks(Coverage(profile),profile); self.receipts={}; self.mutate=None
        self.checks.pipeline=NS(model=self.model,board=Scoreboard('original-final-teaching-controls'),
            raise_failure=lambda:None,source_token=lambda s:s.token)

    def receipt(self,token): return self.receipts[token.sequence]

    def step(self,event=None):
        event=self.event if event is None else event; cycle=self.model.evaluate(event); self.tick+=2
        self.checks.pipeline.current_event=XEvent(event_id=self.tick,tick=self.tick,
            phase=XPhase.RISING_STABLE,kind=XEventKind.CLOCK_RISE)
        actual=actual_live(self.model.sources,cycle.enabled[1])
        if self.mutate is not None: self.mutate(actual)
        self.checks.candidates(dict(observed=dict(early_direction=actual)),event,cycle,self.model,'synthetic',None)
        expected,observed=live_values(self.model.sources,cycle.enabled[1],actual)
        self.checks.pipeline.board.check(expected=expected,actual=observed)
        expected,observed=fast_values(self.model.sources,cycle,actual_fast(self.model.sources,cycle))
        self.checks.pipeline.board.check(expected=expected,actual=observed)
        self.model.advance(event); self.checks.checked(self.tick)
        if cycle.metadata is not None:
            token=cycle.metadata
            self.receipts[token.sequence]=NS(token=token,prediction_tick=self.tick-4,meta_tick=self.tick,
                meta=dict(owner=token.sequence))
        return cycle

    def quiet(self):
        idle=super().quiet()
        for _ in range(128):
            if self.checks.pending is None: return idle
            self.step(idle)
        raise AssertionError('original expected allocation never got actual next-state comparison')

    def resolve(self,source,*args,**kwargs):
        self.checks.plan_resolution(PHASES[len(self.inputs)],self.receipt(source))
        return super().resolve(source,*args,**kwargs)

    def warm(self):
        source=super().warm(); self.checks.early_consumer(self.receipt(source)); return source

    def prepare_control(self):
        weak=self.prepare_late()
        self.checks.stable_predecessor(self.receipt(self.anchor))
        self.checks.weak_consumer(self.receipt(weak))

    async def teach(self):
        self.early_enabled(True); accepted=self.checks.open_original(); self.restart()
        for _ in range(256):
            self.step()
            if accepted.done(): break
        else: raise AssertionError('qualified original S1 was never accepted')
        event=self.event if self.profile.flowing else replace(self.event,prediction_ready=False)
        for _ in range(128):
            self.step(event)
            if self.checks.repair is not None: break
        else: raise AssertionError('original S3 did not repair')
        receipt=self.receipts[self.checks.selected.sequence]
        self.checks.window_receipt(receipt); self.quiet()
        assert self.checks.confirmed is not None

    def consume_new(self):
        # S3 itself restores the old Ahead read ancestor. A second redirect
        # would deliberately discard precisely the recovery being verified.
        record=self.checks.confirmed
        def learned(token):
            value=provider(self.model.sources,token)
            return value is not None and value.table==0 and value.counter<4 and (value.index,value.tag)==(record['index'],record['tag'])
        token=self.source(learned)
        self.checks.negative_consumer(self.receipt(token))

    async def complete(self):
        self.prepare_control(); await self.teach(); self.consume_new()


@pytest.mark.parametrize('profile',PROFILES)
async def test_original_S3_teaching_closes_only_with_actual_state_and_new_consumer(profile):
    p=Program(profile); await p.complete(); c=p.checks
    assert c.coverage.groups['checked'].coverage==0
    c.finish()
    assert c.closed and c.coverage.closed and set(c.reached_rules)==set(RULES)
    assert c.repair['prediction_ready']==p.profile.flowing
    assert c.confirmed['owner']==c.repair['owner'] and c.final['provider']['counter']<4


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('fault',('consumer','teacher','weak-control','actual-confirmation','wrong-owner',
    'receipt-copy','public-metadata','ahead-snapshot','short-snapshot','tage-read','tage-resolved','consumer-report'))
async def test_missing_or_rebound_original_evidence_cannot_get_checked_credit(profile,fault):
    p=Program(profile); await p.complete(); c=p.checks
    if fault=='consumer': c.consumer=None
    elif fault=='teacher': c.teacher=None
    elif fault=='weak-control': c.weak=None
    elif fault=='actual-confirmation': c.pending=dict(expected_only=True)
    elif fault=='wrong-owner': c.confirmed['owner']+=1
    elif fault=='consumer-report': c.final['provider']['counter']^=1
    else:
        key=next(iter(c.saved)); source,token,snapshots,metadata=c.saved[key]
        if fault=='receipt-copy': source.token=replace(token)
        elif fault=='public-metadata': source.meta=dict(corrupted=True)
        else:
            domain=('ahead-snapshot','short-snapshot','tage-read','tage-resolved').index(fault)
            broken=list(snapshots); broken[domain]=None
            c.saved[key]=(source,token,tuple(broken),metadata)
    with pytest.raises(AssertionError): c.finish()
    assert c.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
async def test_unrelated_actual_protection_corruption_fails_before_teaching_credit(profile):
    p=Program(profile); p.prepare_control()
    def corrupt(actual):
        values=[list(t) for t in actual['useful']]; values[0][400]^=1
        actual['useful']=tuple(tuple(t) for t in values)
    p.mutate=corrupt
    with pytest.raises(AssertionError): await p.teach()
    assert p.checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile,rule',[(p,r) for p in PROFILES for r in RULES])
def test_each_human_semantic_obligation_is_required_for_atomic_closure(profile,rule):
    coverage=Coverage(profile)
    for required in RULES:
        if required!=rule:
            coverage.record('reached',required,10); coverage.record('checked',required,20)
    with pytest.raises(AssertionError): coverage.finish()
    assert coverage.groups['checked'].coverage==0


def test_cases_hide_clock_phase_IO_and_parallel_task_plumbing():
    forbidden={'RisingEdge','FallingEdge','ClockCycles','get_','set_','gather','create_task'}
    for name in ('bpu/case/late_correction_learning.py','tests/bpu/testcase/test_late_correction_learning.py'):
        tree=ast.parse(Path(name).read_text())
        assert not {n.id for n in ast.walk(tree) if isinstance(n,ast.Name)} & forbidden
        assert not {n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)} & forbidden


@pytest.mark.parametrize('phase',(XPhase.DRIVE_STABLE,XPhase.EXTERNAL))
async def test_pre_edge_or_external_notification_cannot_complete_actual_acceptance(phase):
    p=Program(PROFILES[0]); p.prepare_control(); p.early_enabled(True)
    accepted=p.checks.open_original(); p.restart()
    original=p.checks.checked
    def wrong_event(tick,*args):
        if p.checks.candidate is not None:
            p.checks.pipeline.current_event=XEvent(event_id=tick,tick=tick,phase=phase,kind=XEventKind.EXTERNAL)
        return original(tick,*args)
    p.checks.checked=wrong_event
    with pytest.raises(AssertionError):
        for _ in range(256): p.step()
    assert not accepted.done() and p.checks.coverage.groups['checked'].coverage==0
