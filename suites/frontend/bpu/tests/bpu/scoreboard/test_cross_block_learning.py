"""Full independent control flow and adversarial ownership/actual-state controls."""
import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard
from bpuverify.bpu.model.cross_block_learning import PROFILES,RULES,program
from bpuverify.bpu.model.early_direction_sources import EarlyDirectionSources
from bpuverify.bpu.model.pipeline import Redirect,Resolution,Outcome
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.early_opposition import provider
from bpuverify.bpu.model.early_aging import require_recovery_window
from bpuverify.bpu.model.path_history import WIDTH,LAYOUT,SHIFT
from bpuverify.bpu.checker.cross_block_learning import Checks
from bpuverify.bpu.checker.early_direction import live_values,fast_values
from bpuverify.bpu.coverage.cross_block_learning import Coverage
from tests.bpu.scoreboard.test_semantic_pipeline import boot
from tests.bpu.scoreboard.test_ahead_sources import ENABLED
from tests.bpu.scoreboard.test_early_direction_checking import actual_live,actual_fast


class Program:
    def __init__(self,profile):
        self.program=program(profile); self.model,self.event=boot(EarlyDirectionSources(),pc=self.program.a)
        self.event=replace(self.event,enabled=ENABLED)
        while self.model.control_pipe[-1]!=ENABLED: self.model.advance(replace(self.event,reset=True))
        self.tick=0; self.checks=Checks(Coverage(profile),profile); self.mutate=None
        self.checks.pipeline=NS(model=self.model,board=Scoreboard('independent-cross-block-controls'),
            raise_failure=lambda:None,source_token=lambda source:source.token)
    def step(self,event=None):
        event=self.event if event is None else event; cycle=self.model.evaluate(event); self.tick+=2
        actual=actual_live(self.model.sources,cycle.enabled[1])
        if self.mutate is not None: self.mutate(actual)
        self.checks.candidates(dict(observed=dict(early_direction=actual)),event,cycle,self.model,'synthetic',None)
        expected,observed=live_values(self.model.sources,cycle.enabled[1],actual)
        self.checks.pipeline.board.check(expected=expected,actual=observed)
        expected,observed=fast_values(self.model.sources,cycle,actual_fast(self.model.sources,cycle))
        self.checks.pipeline.board.check(expected=expected,actual=observed)
        self.model.advance(event); self.checks.checked(self.tick); return cycle
    def quiet(self):
        idle=replace(self.event,prediction_ready=False)
        for _ in range(128):
            self.step(idle)
            if self.model.stages[1:]==(None,None) and not self.model.sources.main_pending() and self.checks.pending is None: return idle
        raise AssertionError('cross-block original effects did not become compared')
    def source(self,pc,predicate=lambda _:True):
        for _ in range(256):
            token=self.step().metadata
            if token is not None and token.pc==pc and token.lookup is not None and predicate(token):
                result=NS(token=token,prediction_tick=self.tick-4,meta_tick=self.tick,meta=dict(owner=token.sequence))
                self.quiet(); return result
        raise AssertionError(('no declared qualified original',pc))
    def from_a(self,source):
        idle=self.quiet(); assert source.token.pc==self.program.a
        require_recovery_window(self.model.history.taken_edges,source.token.history.taken_edges,
            capacity=WIDTH,history_bits=max(length for length,_ in LAYOUT),shift=SHIFT)
        self.step(replace(idle,redirect=Redirect(source.token.history,(self.program.a//8)*8+4,self.program.b,True)))
    def query_successor(self,source):
        self.from_a(source); return self.source(self.program.b)
    def resolve(self,phase,source):
        self.checks.plan_resolution(phase,source)
        pc,position,target,kind,taken=self.program.resolution(phase)
        idle=self.quiet(); active=phase in ('not-taken','fallback') and self.program.flowing
        request=Resolution(source.token.history,pc,(Outcome(position,target,Kind(kind),taken,mispredict=True),),origin=source.token)
        self.step(replace(self.event if active else idle,feedback=request)); self.quiet()
    def prepare(self):
        a=self.source(self.program.a); self.anchor=a; self.resolve('predecessor',a)
        b=self.query_successor(a); self.resolve('conditional',b)
        self.from_a(a); early_a=self.source(self.program.a,lambda token:token.early.source=='ahead')
        self.checks.early_consumer(early_a); self.anchor=early_a
        self.from_a(self.anchor); early_b=self.source(self.program.b,lambda token:token.early.source=='ahead')
        self.checks.early_consumer(early_b)
        self.anchor=self.source(self.program.a,lambda token:token.early.source=='ahead'); self.checks.save(self.anchor)
        self.resolve('not-taken',early_b)
        fallback=self.query_successor(self.anchor); self.resolve('fallback',fallback)
        self.anchor=self.source(self.program.a,lambda token:token.early.source=='ahead'); self.checks.save(self.anchor)
    def consume(self):
        self.from_a(self.anchor)
        def qualified(token):
            value=provider(self.model.sources,token)
            return value is not None and value.table==0 and value.position==2 and value.counter<4
        source=self.source(self.program.b,qualified); self.checks.negative_consumer(source); return source
    def complete(self): self.prepare(); return self.consume()


@pytest.mark.parametrize('profile',PROFILES)
def test_real_cross_block_learning_has_actual_confirmation_and_new_consumer(profile):
    p=Program(profile); p.complete(); c=p.checks
    assert c.coverage.groups['checked'].coverage==0
    c.finish(); assert c.closed and c.coverage.closed
    assert c.final['provider']['index']>=128 and c.final['provider']['counter']<4
    assert c.final['allocation']['written_tick']+2==c.final['allocation']['actual_confirmation_tick']
    assert c.final['read_ancestor']['pc']==p.program.a and c.final['read_ancestor']['matching_pc']==p.program.b


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('missing',('consumer','actual-allocation','early-predecessor','input','metadata','snapshot','rebound-original','consumer-report'))
def test_incomplete_or_rebound_program_never_gets_checked_credit(profile,missing):
    p=Program(profile); p.complete(); c=p.checks
    if missing=='consumer': c.consumer=None
    elif missing=='actual-allocation': c.pending=dict(not_confirmed=True)
    elif missing=='early-predecessor': c.early.pop(p.program.a)
    elif missing=='input': c.inputs.pop()
    elif missing=='consumer-report': c.final['provider']['counter']^=1
    else:
        key=next(iter(c.saved)); source,token,snapshot,meta=c.saved[key]
        if missing=='metadata': source.meta=dict(corrupted=True)
        elif missing=='snapshot': c.saved[key]=source,token,replace(snapshot,end_position=0),meta
        else: source.token=replace(token)
    with pytest.raises(AssertionError): c.finish()
    assert c.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
def test_equal_copied_read_ancestor_cannot_replace_the_actual_A_original(profile):
    p=Program(profile); p.prepare(); c=p.checks
    original=c.frame_origin
    def copied(frame):
        origin=original(frame)
        return dict(origin,token=replace(origin['token']))
    c.frame_origin=copied
    with pytest.raises(AssertionError): p.consume()
    assert c.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('fault',('provider-counter','unexpected-protection'))
def test_actual_payload_and_full_protection_are_not_expected_only_credit(profile,fault):
    p=Program(profile); p.prepare(); seen=[]
    def corrupt(actual):
        if fault=='unexpected-protection':
            rows=[list(row) for row in actual['useful']]; rows[0][400]=3; actual['useful']=tuple(tuple(row) for row in rows); seen.append(p.tick)
        else:
            for entry in actual['meta']['entries']:
                if entry['valid'] and entry['hit'] and entry['provider']==0 and entry['position']==2:
                    entry['counter']^=1; seen.append(p.tick)
    p.mutate=corrupt
    with pytest.raises(AssertionError): p.consume()
    assert seen and p.checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile,missing',[(p,r) for p in PROFILES for r in RULES])
def test_each_complete_program_obligation_is_required(profile,missing):
    coverage=Coverage(profile)
    for rule in RULES:
        if rule!=missing: coverage.record('reached',rule,10); coverage.record('checked',rule,20)
    with pytest.raises(AssertionError): coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
def test_old_cold_original_outside_physical_history_window_is_rejected_before_drive(profile):
    p=Program(profile); p.complete(); old=p.checks.plans['predecessor']; before=p.tick
    for _ in range(64):
        if (p.model.history.taken_edges-old.token.history.taken_edges)*SHIFT>WIDTH-max(length for length,_ in LAYOUT): break
        p.step()
    else: raise AssertionError('real loop did not advance beyond old checkpoint retention')
    with pytest.raises(ValueError,match='outside retained history window'): p.from_a(old)
    assert p.tick>=before and p.checks.coverage.groups['checked'].coverage==0


def test_cases_hide_clocks_raw_IO_and_task_scheduling():
    for name in ('bpuverify/bpu/case/cross_block_learning.py','tests/bpu/testcase/test_cross_block_learning.py'):
        tree=ast.parse(Path(name).read_text()); forbidden={'RisingEdge','FallingEdge','ClockCycles','get_','set_','gather','create_task'}
        assert not {n.id for n in ast.walk(tree) if isinstance(n,ast.Name)} & forbidden
        assert not {n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)} & forbidden
