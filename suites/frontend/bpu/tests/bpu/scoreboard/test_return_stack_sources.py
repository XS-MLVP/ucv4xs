"""Semantic calls, returns and exact originals in the nine-model pipeline."""
from copy import deepcopy
from dataclasses import replace

import pytest

from suites.frontend.bpu.bpu.model.pipeline import Commit, Outcome, Redirect
from suites.frontend.bpu.bpu.model.return_stack_sources import ReturnStackSources
from suites.frontend.bpu.bpu.model.selection import Kind, StackAction
from tests.bpu.scoreboard._statistical_joint_program import Program


class CallProgram(Program):
    def __init__(self):
        super().__init__(positive=True,anchor_pc=0x40001000,pc=0x40002000,sources=ReturnStackSources())

    def prepare(self):
        call=self.query(self.a)
        self.feedback(call,Outcome(2,self.b,Kind.DIRECT,True,StackAction.CALL,mispredict=True))
        ret=self.query(self.b)
        self.feedback(ret,Outcome(2,self.x,Kind.INDIRECT,True,StackAction.RETURN,mispredict=True))
        return call,ret

    def enable_ras(self):
        self.quiet()
        self.event=replace(self.event,enabled=(*self.event.enabled[:6],True))
        for _ in range(3):
            self.step(replace(self.event,prediction_ready=False))

    def call_and_return(self):
        start=len(self.records)
        call=self.query(self.a)
        returns=[c.metadata for c in self.records[start:] if c.metadata is not None and c.metadata.pc==self.b]
        assert returns
        return call,returns[0]


def states(p):
    return tuple(deepcopy(getattr(p.bank,n).state()) for n in
        ('micro','main','ahead','short','tage','indirect','sc','ras','micro_ras')),p.model.state()


def test_real_semantic_learning_drives_owned_call_then_return_not_the_static_target():
    p=CallProgram()
    p.prepare()
    p.enable_ras()
    call,ret=p.call_and_return()
    a,b=p.bank.return_snapshot(call),p.bank.return_snapshot(ret)
    assert a.decision.branch.action==StackAction.CALL
    assert len(a.original.program.frames)==1
    assert b.decision.branch.action==StackAction.RETURN
    assert b.decision.branch.target==p.a+3 and b.decision.branch.target!=p.x
    assert b.decision.source=='return-stack'
    assert b.original.program.head.address==2*(p.a+3)
    assert len(p.bank.ras.program.frames)==1


def test_all_nine_algorithms_advance_once_and_forecasts_change_none(monkeypatch):
    p=CallProgram()
    names=('micro','main','ahead','short','tage','indirect','sc','ras','micro_ras')
    counts=dict.fromkeys(names,0)
    for name in names:
        obj=getattr(p.bank,name)
        advance=obj.advance
        def counted(*args,_name=name,_advance=advance,**kwargs):
            counts[_name]+=1
            return _advance(*args,**kwargs)
        monkeypatch.setattr(obj,'advance',counted)
    for _ in range(8):p.step()
    assert counts==dict.fromkeys(names,8)
    before=states(p)
    for _ in range(3):p.model.evaluate(p.event)
    assert states(p)==before


@pytest.mark.parametrize('ending',('copy','foreign','release','reset'))
def test_stack_originals_share_the_exact_pipeline_lifetime(ending):
    p=CallProgram()
    token=p.query(p.b)
    p.bank.return_snapshot(token)
    if ending=='copy':token=replace(token,history=replace(token.history))
    elif ending=='foreign':token=CallProgram().anchor
    elif ending=='release':p.model.retire_source(token.sequence)
    else:p.step(replace(p.event,reset=True))
    with pytest.raises(ValueError,match='absent|retired|original'):
        p.bank.return_snapshot(token)


def test_call_and_return_retire_once_by_exact_original_then_restore_committed_sentinel():
    p=CallProgram();p.prepare();p.enable_ras()
    call,ret=p.call_and_return()
    idle=p.quiet()
    for token,action in ((call,StackAction.CALL),(ret,StackAction.RETURN)):
        p.step(replace(idle,commit=Commit(token,action)))
        with pytest.raises(ValueError,match='pending return-stack'):
            p.model.retire_source(token.sequence)
        assert p.model.published[token.sequence] is token
        p.step(idle)
    assert p.bank.ras.retirements==2 and p.bank.ras.committed_head==0
    before=states(p)
    with pytest.raises(ValueError,match='twice'):
        p.step(replace(idle,commit=Commit(ret,StackAction.RETURN)))
    assert states(p)==before


def test_recovery_replays_own_call_and_cancels_the_younger_return_before_fresh_consumer():
    p=CallProgram();p.prepare();p.enable_ras()
    call,ret=p.call_and_return()
    idle=p.quiet()
    original=p.bank.return_snapshot(call)
    p.step(replace(idle,redirect=Redirect(call.history,p.a+2,p.b,True,Kind.DIRECT,StackAction.CALL)))
    with pytest.raises(ValueError,match='pending return-stack'):
        p.model.retire_source(call.sequence)
    p.step(idle)
    assert p.bank.ras.program.head.address==2*(p.a+3)
    assert p.bank.return_snapshot(call).original is original.original
    before=states(p)
    with pytest.raises(ValueError,match='cancelled'):
        p.step(replace(idle,commit=Commit(ret,StackAction.RETURN)))
    assert states(p)==before
    fresh=p.consume(p.b)
    assert p.bank.return_snapshot(fresh).decision.branch.target==p.a+3


@pytest.mark.parametrize('fault',('copy','foreign','release','unpublished'))
def test_invalid_commit_changes_neither_tokens_nor_any_predictor(fault):
    p=CallProgram()
    token=p.query(p.b)
    if fault=='copy':token=replace(token)
    elif fault=='foreign':token=CallProgram().anchor
    elif fault=='release':p.model.retire_source(token.sequence)
    else:token=p.model.stages[0]
    before=states(p)
    with pytest.raises(ValueError,match='exact published'):
        p.step(replace(p.event,commit=Commit(token,StackAction.NONE)))
    assert states(p)==before


@pytest.mark.parametrize('service',(False,True))
def test_ittage_publication_valid_is_current_service_not_the_old_query_enable(service):
    p=CallProgram()
    token=p.query(p.b)
    expected=p.bank.defined_ittage_metadata(token,service_enabled=service)
    assert expected['valid']==int(service)
    if not service:
        assert expected==dict(valid=0)
    # Reading another service boundary never rewrites this published original.
    before=p.bank.defined_ittage_metadata(token)
    p.bank.defined_ittage_metadata(token,service_enabled=not service)
    assert p.bank.defined_ittage_metadata(token)==before


from suites.frontend.bpu.bpu.coverage.owned_return_stack import OwnedReturnCoverage
from suites.frontend.bpu.bpu.model.owned_return_stack import PROGRAMS


@pytest.mark.parametrize('program,missing',[(p,r) for p in PROGRAMS for r in p.rules],
    ids=[p.label+'.'+r for p in PROGRAMS for r in p.rules])
def test_any_unchecked_lifetime_obligation_prevents_native_checked_credit(program,missing):
    coverage=OwnedReturnCoverage(program)
    for rule in program.rules:
        if rule!=missing:coverage.record(rule)
    with pytest.raises(AssertionError,match='all owned return-stack'):
        coverage.finish()
    assert not coverage.closed and coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_one_complete_program_cannot_award_another_original_lifetime(program):
    coverage=OwnedReturnCoverage(program)
    for rule in program.rules:coverage.record(rule)
    coverage.finish()
    counts=coverage.groups['checked'].report()['points'][0]['counts']
    assert {n for n,v in counts.items() if v}=={program.label+'.'+r for r in program.rules}
