"""Synthetic public-source faults qualify the adapter, not DUT coverage."""
import ast
from collections import Counter,deque
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.checker.micro_capacity import MicroCapacityChecks,ROLES
from suites.frontend.bpu.bpu.coverage.micro_capacity import MicroCapacityCoverage,capacity_coverage
from suites.frontend.bpu.bpu.model.selection import Kind,StackAction,fallthrough
from suites.frontend.bpu.ubtb.model.semantic import UbtbEvents,UbtbReference
from suites.frontend.bpu.ubtb.transaction.types import BranchTraining,PredictRequest


PC = 0x40000800


def fixture():
    micro = UbtbReference()
    program = {PC+i*128:(PC+0x20000+i*32,3+8*(i%2)) for i in range(micro.capacity+1)}
    pipeline = NS(model=NS(sources=NS(micro=micro)),records=deque(maxlen=8),counts=Counter(),
        last_resolution=None,raise_failure=lambda:None)
    coverage = MicroCapacityCoverage()
    return MicroCapacityChecks(pipeline,program,coverage)


def public(checks,pc,role):
    tick = checks.last_source_tick+2
    target,taken,position = (*checks.program[pc][:1],1,checks.program[pc][1]) if ROLES[role] else (
        fallthrough(pc).branch.target,0,fallthrough(pc).branch.position)
    expected = dict(pc=pc,target=target,taken=taken,position=position,repair2=0,repair3=0)
    checks.pipeline.records.append(dict(tick=tick,expected=dict(prediction=expected)))
    return NS(prediction_tick=tick,meta_tick=tick+4,meta=NS(perf=NS(start_pc=pc)),prediction=NS(
        start_pc=pc,target=target,taken=taken,position=position,s2_override=0,s3_override=0))


def learn(checks,pc):
    target,position = checks.program[pc]
    micro = checks.pipeline.model.sources.micro
    micro.advance(UbtbEvents(fast_feedback=BranchTraining(pc*2,target*2,1,position,2,0,1)))
    micro.advance(UbtbEvents())


def prepared():
    checks = fixture()
    for pc in tuple(checks.program)[:-1]:
        checks.source(public(checks,pc,'cold'),pc,'cold')
        learn(checks,pc)
    for pc in tuple(checks.program)[:-1]:checks.source(public(checks,pc,'initial-resident'),pc,'initial-resident')
    checks.source(public(checks,checks.new_pc,'cold'),checks.new_pc,'cold')
    micro = checks.pipeline.model.sources.micro
    protected = next(pc for pc in checks.initial if micro._find(pc*2)==micro.victim())
    checks.plan_protection(protected)
    checks.source(public(checks,protected,'protect'),protected,'protect')
    micro.advance(UbtbEvents(predict=PredictRequest(protected*2)))
    micro.advance(UbtbEvents())
    victim = next(pc for pc in checks.initial if micro._find(pc*2)==micro.victim())
    checks.plan_replacement(victim)
    return checks


def accepted(checks):
    target,position = checks.program[checks.new_pc]
    checks.pipeline.counts['feedback'] += 1
    checks.pipeline.last_resolution = 500,NS(pc=checks.new_pc,branches=(NS(target=target,position=position,
        kind=Kind.DIRECT,taken=True,mispredict=True,action=StackAction.NONE),))
    learn(checks,checks.new_pc)
    checks.replacement_accepted()


def proof(checks,*,omit=None):
    if omit!='victim':checks.source(public(checks,checks.victim,'evicted'),checks.victim,'evicted')
    if omit!='new':checks.source(public(checks,checks.new_pc,'new'),checks.new_pc,'new')
    for pc in sorted(checks.initial-{checks.victim}):
        if omit=='protected' and pc==checks.protected:continue
        if omit=='neighbor' and pc!=checks.protected:continue
        checks.source(public(checks,pc,'survivor'),pc,'survivor')


def test_complete_protocol_needs_capacity_real_feedback_and_every_survivor():
    checks = prepared()
    assert checks.coverage.groups['checked'].coverage==pytest.approx(100/6)
    accepted(checks)
    assert checks.coverage.groups['checked'].coverage==pytest.approx(100/6)
    proof(checks)
    checks.finish()
    assert len(checks.sources)==99
    assert all(group.coverage==100 for group in checks.coverage.groups.values())


@pytest.mark.parametrize('fault',('pc','target','taken','position','s2','s3','meta-pc','meta-tick','source-tick'))
def test_corrupt_public_source_latches_first_failure_without_golden_resynchronization(fault):
    checks = fixture()
    pc = next(iter(checks.program))
    tx = public(checks,pc,'initial-resident')
    if fault=='pc':tx.prediction.start_pc ^= 1
    elif fault=='target':tx.prediction.target ^= 1
    elif fault=='taken':tx.prediction.taken ^= 1
    elif fault=='position':tx.prediction.position ^= 1
    elif fault=='s2':tx.prediction.s2_override = 1
    elif fault=='s3':tx.prediction.s3_override = 1
    elif fault=='meta-pc':tx.meta.perf.start_pc ^= 1
    elif fault=='meta-tick':tx.meta_tick += 2
    else:tx.prediction_tick += 1
    state = deepcopy(checks.pipeline.model.sources.micro.state())
    with pytest.raises(AssertionError) as first:checks.source(tx,pc,'initial-resident')
    with pytest.raises(AssertionError) as second:checks.source(public(checks,pc,'initial-resident'),pc,'initial-resident')
    assert first.value is second.value
    assert checks.pipeline.model.sources.micro.state()==state
    assert not checks.sources and checks.coverage.groups['checked'].coverage==0


def test_reusing_one_source_cannot_fake_distinct_real_consumers():
    checks = fixture()
    pc = next(iter(checks.program))
    tx = public(checks,pc,'initial-resident')
    checks.source(tx,pc,'initial-resident')
    with pytest.raises(AssertionError,match='never reused'):checks.source(tx,pc,'initial-resident')


@pytest.mark.parametrize('field',('target','position','kind','taken','mispredict','action','pc','no-accept','extra-accept'))
def test_wrong_or_merely_planned_feedback_is_not_a_replacement_event(field):
    checks = prepared()
    target,position = checks.program[checks.new_pc]
    branch = NS(target=target,position=position,kind=Kind.DIRECT,taken=True,mispredict=True,action=StackAction.NONE)
    resolution = NS(pc=checks.new_pc,branches=(branch,))
    checks.pipeline.counts['feedback']=1
    if field=='pc':resolution.pc ^= 1
    elif field=='no-accept':checks.pipeline.counts['feedback']=0
    elif field=='extra-accept':checks.pipeline.counts['feedback']=2
    else:setattr(branch,field,getattr(branch,field)^1)
    checks.pipeline.last_resolution = 500,resolution
    with pytest.raises(AssertionError):checks.replacement_accepted()
    assert not checks.admitted
    assert 'rule.full-cache-replacement' in checks.coverage.groups['reached'].uncovered()


@pytest.mark.parametrize('missing',('victim','new','protected','neighbor'))
def test_replacement_checked_credit_requires_the_complete_consumer_footprint(missing):
    checks = prepared()
    accepted(checks)
    proof(checks,omit=missing)
    assert 'rule.full-cache-replacement' in checks.coverage.groups['checked'].uncovered()
    with pytest.raises(AssertionError):checks.finish()


def test_protection_must_name_the_old_owned_victim_not_any_recent_entry():
    checks = fixture()
    for pc in checks.initial:learn(checks,pc)
    micro = checks.pipeline.model.sources.micro
    wrong = next(pc for pc in checks.initial if micro._find(pc*2)!=micro.victim())
    with pytest.raises(AssertionError):checks.plan_protection(wrong)


@pytest.mark.parametrize('role,pc_kind',(('wrong','old'),('new','old'),('survivor','new'),('evicted','new')))
def test_unaccepted_or_wrong_role_consumer_fails_closed(role,pc_kind):
    checks = fixture()
    pc = checks.new_pc if pc_kind=='new' else next(iter(checks.initial))
    with pytest.raises(ValueError):checks.source(public(checks,pc,'cold'),pc,role)


def test_case_contains_no_edge_get_set_or_gather_and_checker_is_not_in_testcase():
    tree = ast.parse(Path('bpu/case/micro_capacity.py').read_text())
    for node in ast.walk(tree):
        assert not isinstance(node,ast.ClassDef)
        if isinstance(node,ast.Call):
            name = node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','GetInternalSignal'}
    assert capacity_coverage('checked').coverage==0
    with pytest.raises(ValueError):capacity_coverage('phase')
