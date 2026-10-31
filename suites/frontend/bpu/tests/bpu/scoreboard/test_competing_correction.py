"""Independent event/lifetime controls; synthetic data has no DUT credit."""
from suites.frontend.bpu.models.configuration import TAGE_ALLOCATION_WAIT
import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard,XEvent,XPhase,XEventKind
from suites.frontend.bpu.bpu.model.competing_correction import program,PROFILES,RULES,PHASES
from suites.frontend.bpu.bpu.model.pipeline import Resolution,Outcome,Redirect
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.early_aging import require_recovery_window
from suites.frontend.bpu.bpu.model.path_history import WIDTH,LAYOUT,SHIFT
from suites.frontend.bpu.tage.model.semantic import TABLES,HISTORIES
from suites.frontend.bpu.bpu.checker.competing_correction import Checks
from suites.frontend.bpu.bpu.checker.early_direction import live_values,fast_values
from suites.frontend.bpu.bpu.coverage.competing_correction import Coverage
from tests.bpu.scoreboard.test_early_late_sources import Program as Foundation
from tests.bpu.scoreboard.test_early_direction_checking import actual_live,actual_fast


class Program(Foundation):
    def __init__(self,profile):
        self.program=program(profile); super().__init__(self.program.b)
        self.checks=Checks(Coverage(profile),profile); self.receipts={}; self.mutate=None
        self.checks.pipeline=NS(model=self.model,board=Scoreboard('competing-original-controls'),
            raise_failure=lambda:None,source_token=lambda source:source.token)
    def step(self,event=None):
        event=self.event if event is None else event; cycle=self.model.evaluate(event); self.tick+=2
        self.checks.pipeline.current_event=XEvent(event_id=self.tick,tick=self.tick,phase=XPhase.RISING_STABLE,kind=XEventKind.CLOCK_RISE)
        actual=actual_live(self.model.sources,cycle.enabled[1])
        if self.mutate is not None:self.mutate(actual)
        self.checks.candidates(dict(observed=dict(early_direction=actual)),event,cycle,self.model,'synthetic',None)
        wanted,observed=live_values(self.model.sources,cycle.enabled[1],actual)
        self.checks.pipeline.board.check(expected=wanted,actual=observed)
        wanted,observed=fast_values(self.model.sources,cycle,actual_fast(self.model.sources,cycle))
        self.checks.pipeline.board.check(expected=wanted,actual=observed)
        self.model.advance(event);self.checks.checked(self.tick)
        if cycle.metadata is not None:
            t=cycle.metadata;self.receipts[t.sequence]=NS(token=t,prediction_tick=self.tick-4,meta_tick=self.tick,meta=dict(owner=t.sequence))
        return cycle
    def quiet(self):
        idle=super().quiet()
        for _ in range(128):
            if self.checks.pending is None and self.checks.restore_pending is None:return idle
            self.step(idle)
        raise AssertionError('actual restoration or learning has not been compared')
    def restart(self):
        idle=self.quiet();t=self.anchor
        require_recovery_window(self.model.history.taken_edges,t.history.taken_edges,
            capacity=WIDTH,history_bits=max(n for n,_ in LAYOUT),shift=SHIFT)
        self.step(replace(idle,redirect=Redirect(t.history,(self.a//8)*8+6,self.pc,True)))
    def resolve_owned(self,phase,source):
        self.checks.plan_resolution(phase,self.receipts[source.sequence])
        pc,position,target,kind,taken,wrong=self.program.resolution(phase);idle=self.quiet()
        request=Resolution(source.history,pc,(Outcome(position,target,Kind(kind),taken,mispredict=wrong),),origin=source)
        if phase=='not-taken':
            feedback=self.model.sources.feedback_for(request)
            for _ in range(TAGE_ALLOCATION_WAIT):
                candidate=self.model.sources.tage.allocation_at_next_accept(feedback)
                if candidate is not None and candidate[0]<TABLES-1:break
                self.step(idle)
            else:raise AssertionError('no real room for later history specialization')
        self.step(replace(idle,feedback=request));self.inputs.append(request);self.quiet()
    def prepare(self):
        self.anchor=self.source(pc=self.a);self.resolve_owned('predecessor',self.anchor)
        source=self.query();self.resolve_owned('conditional',source)
        self.query();self.restart()
        seed=self.source(lambda t:t.early.source in ('ahead','ahead-direction') and t.early.branch.position==2)
        self.checks.early_consumer(self.receipts[seed.sequence])
        self.anchor=self.source(lambda t:t.early.source=='ahead' and t.early.branch.position==6,pc=self.a)
        self.early_enabled(False)
        for phase in ('not-taken','strengthen-negative','fallback'):
            source=self.query();self.resolve_owned(phase,source)
        self.restart();self.anchor=self.source(lambda t:t.history.history%(1<<max(HISTORIES))==self.program.stable_predecessor_history,pc=self.a)
        self.checks.stable_predecessor(self.receipts[self.anchor.sequence])
        source=self.query();self.resolve_owned('late-surprise',source)
        weak=self.query();self.checks.weak_consumer(self.receipts[weak.sequence])
    async def hold_old(self):
        self.early_enabled(True);prepared=self.checks.open_preparation();self.restart()
        for _ in range(256):
            self.step()
            if prepared.done():break
        else:raise AssertionError('no actual predecessor issued a qualified old lookup')
        self.quiet();assert self.model.stages[0] is self.checks.prepared
        self.resolve_owned('young-discovery',self.anchor)
    async def compete(self):
        released=self.checks.open_release()
        for _ in range(128):
            self.step()
            if released.done():break
        else:raise AssertionError('both independent sources were not accepted')
        event=self.event if self.program.flowing else replace(self.event,prediction_ready=False)
        for _ in range(128):
            self.step(event)
            if self.checks.repair is not None:break
        else:raise AssertionError('real old S3 and young S2 never competed')
        self.checks.save(self.receipts[self.checks.selected.sequence]);self.quiet()
    def consume(self):
        token=self.source(lambda t:t.history.history==self.checks.repair['winning_history'],pc=self.a)
        self.checks.consume_restored(self.receipts[token.sequence])
    async def complete(self):self.prepare();await self.hold_old();await self.compete();self.consume()


@pytest.mark.parametrize('profile',PROFILES)
async def test_real_old_and_young_corrections_have_one_owned_winning_history(profile):
    p=Program(profile);await p.complete();c=p.checks
    assert c.coverage.groups['checked'].coverage==0
    c.finish();assert c.closed and c.coverage.closed
    assert c.repair['winning_history']!=c.repair['rejected_history']
    assert c.final['history']==c.repair['winning_history'] and c.confirmed['owner']==c.repair['owner']


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('fault',('consumer','actual-restoration','actual-learning','young-learning-owner',
    'old-receipt-copy','metadata','snapshot','winning-history','consumer-history','missing-input'))
async def test_incomplete_or_rebound_originals_cannot_receive_atomic_credit(profile,fault):
    p=Program(profile);await p.complete();c=p.checks
    if fault=='consumer':c.consumer=None
    elif fault=='actual-restoration':c.restoration=None
    elif fault=='actual-learning':c.pending=dict(expected_only=True)
    elif fault=='young-learning-owner':c.confirmed['owner']=c.repair['young_owner']
    elif fault=='winning-history':c.restoration['winning_history']=c.repair['rejected_history']
    elif fault=='consumer-history':c.final['history']=c.repair['rejected_history']
    elif fault=='missing-input':c.inputs.pop()
    else:
        key=next(iter(c.saved));source,token,snapshots,metadata=c.saved[key]
        if fault=='old-receipt-copy':source.token=replace(token)
        elif fault=='metadata':source.meta=dict(corrupted=True)
        else:c.saved[key]=source,token,(None,*snapshots[1:]),metadata
    with pytest.raises(AssertionError):c.finish()
    assert c.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile,rule',[(p,r) for p in PROFILES for r in RULES])
def test_each_original_lifetime_obligation_is_required(profile,rule):
    coverage=Coverage(profile)
    for name in RULES:
        if name!=rule:coverage.record('reached',name,10);coverage.record('checked',name,20)
    with pytest.raises(AssertionError):coverage.finish()
    assert coverage.groups['checked'].coverage==0


def test_instruction_layout_and_case_abstraction_are_semantic():
    for profile in PROFILES:
        p=program(profile)
        assert p.a%8==3 and p.resolution('young-discovery')[1]==3 and p.predecessor_position==6
        assert p.resolution('young-discovery')[1]+2<=p.predecessor_position
    forbidden={'RisingEdge','FallingEdge','ClockCycles','get_','set_','gather','create_task'}
    for name in ('bpu/case/competing_correction.py','tests/bpu/testcase/test_competing_correction.py'):
        tree=ast.parse(Path(name).read_text())
        assert not {n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}&forbidden
        assert not {n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}&forbidden
