"""Consumed resolve arbitrates its own teacher, never a younger original."""
import pytest
from suites.frontend.bpu.bpu.model.micro_sources import MicroSources
from suites.frontend.bpu.bpu.model.path_history import Checkpoint
from suites.frontend.bpu.bpu.model.pipeline import Cycle,Events,Outcome,Resolution,Token
from suites.frontend.bpu.bpu.model.selection import Branch,Choice,Kind
from suites.frontend.bpu.ubtb.model.semantic import UbtbEvents,UbtbReference
from suites.frontend.bpu.ubtb.transaction.types import BranchTraining,UbtbBatchTraining,UbtbBranchFeedback

pytestmark=pytest.mark.toffee_functional_coverage(False)
PC=0x4000
HISTORY=Checkpoint(0,0,0)


def teacher(taken,pc=PC):
    return BranchTraining(pc*2,pc*2,int(taken),1,int(Kind.CONDITIONAL),mispredict=0)


def tick(sources,fast=None,feedback=None,*,consumed=True,enabled=True):
    token=None if fast is None else Token(0,fast.pc//2,HISTORY,None)
    choice=None if fast is None else Choice(Branch(fast.position,fast.target//2,
        Kind(fast.branch_type),bool(fast.taken)),None,'main')
    cycle=Cycle((None,None,token),(None,None,choice),(False,False,False,token is not None),
        (False,False,False),False,False,None,token,PC,(enabled,False,False,False,False,False,False))
    sources.advance(Events(PC,feedback=feedback,feedback_at_edge=consumed),cycle,None)


def warm():
    sources,golden=MicroSources(),UbtbReference()
    for fast in (teacher(True),None):
        tick(sources,fast,consumed=False)
        golden.advance(UbtbEvents(fast_feedback=fast))
    assert sources.micro.state()==golden.state()
    return sources,golden


def resolved(kind,new_pc=False):
    pc=PC+0x40 if new_pc else PC
    taken=kind!='not-taken'
    target=pc+8 if kind=='different-target' else pc
    wrong=kind!='correct'
    value=Resolution(HISTORY,pc,(Outcome(1,target,Kind.CONDITIONAL,taken,mispredict=wrong),))
    batch=UbtbBatchTraining(pc*2,(UbtbBranchFeedback(target*2,int(taken),1,int(Kind.CONDITIONAL),mispredict=int(wrong)),))
    return value,batch


@pytest.mark.parametrize('previous_taken',(False,True))
@pytest.mark.parametrize('next_taken',(False,True))
@pytest.mark.parametrize('kind',('correct','not-taken','different-target'))
@pytest.mark.parametrize('new_pc',(False,True))
def test_consumed_feedback_uses_its_own_admission_view_and_keeps_the_next_teacher(previous_taken,next_taken,kind,new_pc):
    sources,golden=warm()
    previous,current=teacher(previous_taken),teacher(next_taken)
    feedback,batch=resolved(kind,new_pc)
    tick(sources,previous)
    # The real accepted resolve and previous fast teacher share an edge.
    golden.advance(UbtbEvents(fast_feedback=previous,resolve_feedback=batch))
    # At receipt delivery the independent pipeline already presents a younger
    # teacher. That teacher must not be suppressed by the old acceptance.
    tick(sources,current,feedback)
    golden.advance(UbtbEvents(fast_feedback=current))
    assert sources.micro.state()==golden.state()
    tick(sources)
    golden.advance(UbtbEvents())
    assert sources.micro.state()==golden.state()


@pytest.mark.parametrize('previous_taken',(False,True))
@pytest.mark.parametrize('next_taken',(False,True))
def test_forecast_feedback_still_arbitrates_the_current_teacher(previous_taken,next_taken):
    sources,golden=warm()
    feedback,batch=resolved('not-taken')
    for fast,request,wire in ((teacher(previous_taken),None,None),(teacher(next_taken),feedback,batch),(None,None,None)):
        tick(sources,fast,request,consumed=False)
        golden.advance(UbtbEvents(fast_feedback=fast,resolve_feedback=wire))
        assert sources.micro.state()==golden.state()


def test_actual_resolve_decrement_does_not_swallow_a_younger_correct_increment():
    sources,golden=warm()
    old,batch=resolved('not-taken')
    tick(sources,teacher(True))
    tick(sources,teacher(True),old)
    assert sources.micro.entries[0].confidence==2
    assert sources.micro.learning.result.confidence==3
    tick(sources)
    assert sources.micro.entries[0].confidence==3


def test_reset_discards_the_prior_feedback_boundary():
    sources,_=warm()
    tick(sources,teacher(True))
    sources.reset()
    old,_=resolved('not-taken')
    with pytest.raises(ValueError,match='preceding owned boundary'):tick(sources,feedback=old)


@pytest.mark.parametrize('first_kind',('not-taken','different-target'))
@pytest.mark.parametrize('second_kind',('not-taken','different-target'))
def test_adjacent_consumed_feedbacks_are_each_associated_once(first_kind,second_kind):
    sources,golden=warm()
    first,first_batch=resolved(first_kind)
    second,second_batch=resolved(second_kind)
    tick(sources,teacher(True))
    golden.advance(UbtbEvents(fast_feedback=teacher(True),resolve_feedback=first_batch))
    tick(sources,teacher(True),first)
    golden.advance(UbtbEvents(fast_feedback=teacher(True),resolve_feedback=second_batch))
    tick(sources,teacher(True),second)
    golden.advance(UbtbEvents(fast_feedback=teacher(True)))
    assert sources.micro.state()==golden.state()
    tick(sources)
    golden.advance(UbtbEvents())
    assert sources.micro.state()==golden.state()


@pytest.mark.parametrize('previous_enable',(False,True))
def test_consumed_feedback_eligibility_uses_its_own_enable_not_the_next_level(previous_enable):
    sources,golden=warm()
    old,batch=resolved('not-taken')
    tick(sources,teacher(True),enabled=previous_enable)
    golden.advance(UbtbEvents(fast_feedback=teacher(True),resolve_feedback=batch,enabled=previous_enable))
    tick(sources,teacher(True),old,enabled=not previous_enable)
    golden.advance(UbtbEvents(fast_feedback=teacher(True),enabled=not previous_enable))
    assert sources.micro.state()==golden.state()


def test_boundary_amendment_refuses_to_rewrite_already_committed_history():
    sources,_=warm()
    tick(sources,teacher(True))
    sources.micro.recency.older[0]^=1
    old,_=resolved('not-taken')
    with pytest.raises(AssertionError,match='cannot rewrite committed'):tick(sources,feedback=old)


@pytest.mark.parametrize('invalid',(0,1,None,'consumed'))
def test_feedback_boundary_role_must_be_explicitly_boolean(invalid):
    with pytest.raises(ValueError,match='semantic bools'):Events(PC,feedback_at_edge=invalid)
