"""Parent-policy qualification, priority and real failed-allocation aging threshold."""
from copy import deepcopy
import pytest
from bpuverify.bpu.model.phr.model import folds
from bpuverify.bpu.model.bypass.policy import TrainingPolicy
from bpuverify.bpu.model.bypass.policy import derive

def entry(**changes):
    value=dict(valid=0,hit=0,tableId=0,cfiPosition=0,baseTaken=0,predTaken=0,takenCtr_value=3,baseIsStrongBias=0)
    value.update(changes)
    return value

def fast(entries=None,**changes):
    value=dict(pc=0x40010006,position=6,taken=1,branch_type=1,
        meta=dict(abtbResult=entries or [entry(valid=1,cfiPosition=6),entry(),entry(),entry()],
            readIndex=[25,25],foldedPathHistForTrain_hist=[dict(foldedHist=value) for value in folds(31)]))
    value.update(changes)
    return value

def reads(useful=(0,0),**changes):
    values=[dict(hit=0,position=0,useful=value) for value in useful]
    for value in values: value.update(changes)
    return values

@pytest.mark.parametrize("useful,mask",[((0,0),1),((1,0),2),((0,1),1),((1,2),0),((3,3),0)])
def test_allocation_chooses_first_nonuseful_table(useful,mask):
    result=derive(fast(),reads(useful))
    assert result["normal_mask"]==mask
    assert [v["allocate"] for v in result["tables"]]==[int(bool(mask&1)),int(bool(mask&2))]

@pytest.mark.parametrize("provider,mask",[(0,2),(1,0)])
def test_hit_mispredict_cannot_allocate_provider_or_shorter_table(provider,mask):
    result=derive(fast([entry(valid=1,hit=1,tableId=provider,cfiPosition=6),entry(),entry(),entry()]),reads())
    assert result["normal_mask"]==mask and result["tables"][provider]["update"]

def test_equal_mispredict_positions_use_high_way_but_updates_use_low_way():
    entries=[entry(valid=1,hit=1,cfiPosition=6,tableId=0,takenCtr_value=2),
        entry(),entry(),entry(valid=1,hit=1,cfiPosition=6,tableId=1,takenCtr_value=5)]
    result=derive(fast(entries),reads())
    assert result["selected_mispredict_way"]==3
    assert result["tables"][0]["update_counter"]==2 and result["tables"][1]["update_counter"]==5

def test_earliest_position_wins_even_if_its_way_is_higher():
    values=[entry(valid=1,cfiPosition=6,baseTaken=0),entry(),entry(),entry(valid=1,cfiPosition=3,baseTaken=1)]
    assert derive(fast(values),reads())["selected_mispredict_way"]==3

def test_position_mismatch_blocks_update_without_inventing_missing_slot():
    values=[entry(valid=1,hit=1,cfiPosition=6,tableId=1),entry(),entry(),entry()]
    result=derive(fast(values),reads(hit=1,position=7))
    assert not result["tables"][1]["update"]

@pytest.mark.parametrize("pred,base,taken,valid,increase",[(0,0,1,1,0),(1,0,1,1,1),(1,1,1,0,0),(1,1,0,1,0),(0,1,0,1,1)])
def test_complete_useful_qualification(pred,base,taken,valid,increase):
    values=[entry(valid=1,hit=1,cfiPosition=6,tableId=1,predTaken=pred,baseTaken=base),entry(),entry(),entry()]
    value=derive(fast(values,taken=taken),reads())["tables"][1]
    assert (value["useful_valid"],value["useful_increase"])==(valid,increase)

def test_aging_requires_exactly128_qualified_failed_allocations_then_clears():
    model=TrainingPolicy()
    stimulus=fast()
    model.advance(reset=0,enable=1,fast=stimulus,reads=reads((1,2)))
    model.advance(reset=0,enable=1,fast=stimulus,reads=reads((1,2)))
    for _ in range(127): model.advance(reset=0,enable=1,fast=stimulus,reads=reads((1,2)))
    assert model.low_tick==127 and not model.outputs()[0]["age"]
    model.advance(reset=0,enable=1,fast=stimulus,reads=reads((1,2)))
    assert model.low_tick==128 and all(value["age"] for value in model.outputs())
    model.advance(reset=0,enable=1,fast=stimulus,reads=reads((1,2)))
    assert model.low_tick==0 and model.age_pulses==1 and not model.outputs()[0]["age"]

def test_enable_gates_t0_not_already_registered_t1():
    model=TrainingPolicy()
    stimulus=fast()
    model.advance(reset=0,enable=1,fast=stimulus,reads=reads((1,2)))
    model.advance(reset=0,enable=1,fast=stimulus,reads=reads((1,2)))
    model.advance(reset=0,enable=0,fast=None,reads=reads((1,2)))
    assert model.low_tick==1 and model.t1 is None

def test_reset_clears_all_pending_tasks_and_age_counter():
    model=TrainingPolicy()
    model.fast=fast()
    model.t1=derive(fast(),reads((1,2)))
    model.low_tick=128
    model.advance(reset=1,enable=1,fast=fast(),reads=reads((1,2)))
    assert model.fast is model.t1 is None and model.low_tick==0 and model.outputs()[1]["age"]==0
