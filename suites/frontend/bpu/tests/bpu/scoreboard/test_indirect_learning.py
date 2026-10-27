"""Learning credit requires real original-source feedback and all consumers."""
from bpuverify.common.model.configuration import ITTAGE_ALLOCATION_WAIT

from dataclasses import replace
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard

from bpuverify.bpu.checker.indirect_learning import IndirectLearningChecks
from bpuverify.bpu.coverage.indirect_learning import IndirectLearningCoverage
from tests.bpu.scoreboard.test_indirect_sources import prepared,resolution,resolve,ENABLED
from tests.bpu.scoreboard.test_direction_sources import revisit


def fixture():
    model,event,anchor=prepared();pc=anchor.pc
    for _ in range(ITTAGE_ALLOCATION_WAIT):
        token=revisit(model,event,anchor,pc)
        if model.sources.snapshot(token,resolved=True).allocation==4:break
    else:raise AssertionError('cold longest allocation missing')
    retired=[];repairs={}
    pipeline=NS(board=Scoreboard('owned-indirect-learning-contract'),model=model,raise_failure=lambda:None,
        source_token=lambda r:r.token,last_resolution_controls=None,retire_source=retired.append,
        corrections_for_source=lambda r:repairs[r.meta_tick])
    checks=IndirectLearningChecks(pipeline,IndirectLearningCoverage(),pc,4,pc+0x400,pc+0x600)
    source=NS(token=token,prediction_tick=100,meta_tick=104)
    return checks,source,(model,event,anchor),repairs,retired


def program(*,fault=None):
    checks,source,state,repairs,retired=fixture();model,event,anchor=state;pc=anchor.pc
    checks.cold(source)
    steps=((pc+0x400,2,pc+0x400,False),(pc+0x600,1,pc+0x400,True),
        (pc+0x600,0,pc+0x400,True),(pc+0x600,0,pc+0x600,False))
    for ordinal,(target,confidence,expected,repair) in enumerate(steps):
        tick=110+ordinal*30;request=resolution(source.token,target,wrong=True)
        checks.pipeline.last_resolution_controls=(tick,ENABLED)
        if fault=='owner':request=replace(request,origin=replace(source.token))
        elif fault=='target':request=replace(request,branches=(replace(request.branches[0],target=target+1),))
        elif fault=='wrong-flag':request=replace(request,branches=(replace(request.branches[0],mispredict=False),))
        elif fault=='controls':checks.pipeline.last_resolution_controls=(tick,(False,)*7)
        checks.accepted_feedback(source,(tick,request),target)
        resolve(model,event,source.token,target)
        token=revisit(model,event,anchor,pc);source=NS(token=token,prediction_tick=tick+10,meta_tick=tick+14)
        repairs[source.meta_tick]=((source.prediction_tick+2,2),)+(((source.prediction_tick+4,3),) if repair else ())
        if fault=='repair':repairs[source.meta_tick]=()
        checks.consumed(source,confidence=confidence,main=target,target=expected,repair=repair)
        assert checks.coverage.groups['checked'].coverage==0
    if fault=='immutable':checks.metadata[0]['valid']^=1
    checks.finish()
    return checks,retired


def test_complete_original_source_retention_repair_and_retarget_closes_only_after_four_fresh_consumers():
    checks,retired=program()
    assert checks.closed and len(retired)==5
    assert all(group.coverage==100 for group in checks.coverage.groups.values())


@pytest.mark.parametrize('fault',('owner','target','wrong-flag','controls','repair','immutable'))
def test_wrong_learning_or_incomplete_final_repair_never_receives_checked_credit(fault):
    with pytest.raises(AssertionError):program(fault=fault)


def test_empty_or_merely_cold_learning_cannot_finish():
    checks,source,_,_,retired=fixture();checks.cold(source)
    with pytest.raises(AssertionError):checks.finish()
    assert not retired and checks.coverage.groups['checked'].coverage==0
