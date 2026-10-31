"""Synthetic adapter negatives plus independent learning algebra; not DUT credit."""
import ast
from collections import deque
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.checker.micro_forwarding import MicroForwardingChecks
from suites.frontend.bpu.bpu.coverage.micro_forwarding import MicroForwardingCoverage,forwarding_coverage
from suites.frontend.bpu.bpu.model.selection import Kind,StackAction,fallthrough
from suites.frontend.bpu.ubtb.model.semantic import UbtbEvents,UbtbReference
from suites.frontend.bpu.ubtb.transaction.types import BranchTraining


PC,TARGET,POSITION = 0x40000800,0x40020800,5


def fixture():
    micro = UbtbReference()
    pipeline = NS(model=NS(sources=NS(micro=micro)),records=deque(maxlen=8),resolutions=deque(maxlen=8),
        micro_checked=None,raise_failure=lambda:None)
    return MicroForwardingChecks(pipeline,PC,TARGET,POSITION,MicroForwardingCoverage())


def public(checks,hit):
    tick = checks.last_source_tick+10
    branch = fallthrough(PC).branch
    target,position = (TARGET,POSITION) if hit else (branch.target,branch.position)
    value = dict(pc=PC,target=target,taken=int(hit),position=position,repair2=0,repair3=0)
    checks.pipeline.records.append(dict(tick=tick,expected=dict(prediction=value)))
    return NS(prediction_tick=tick,meta_tick=tick+4,meta=NS(perf=NS(start_pc=PC)),prediction=NS(
        start_pc=PC,target=target,taken=int(hit),position=position,s2_override=0,s3_override=0))


def learn(checks,taken):
    micro = checks.pipeline.model.sources.micro
    micro.advance(UbtbEvents(fast_feedback=BranchTraining(PC*2,TARGET*2,int(taken),POSITION,2,0,1)))
    micro.advance(UbtbEvents())


def compared(checks,tick):
    # Synthetic actuals solely for qualifying adapter failures.
    checks.pipeline.micro_checked = tick,tuple(entry.confidence for entry in checks.pipeline.model.sources.micro.entries)


def weak(*,qualify=True):
    checks = fixture()
    learn(checks,True)
    for _ in range(2):
        source = public(checks,True)
        checks.source(source,hit=True,origin=True)
        learn(checks,False)
    compared(checks,checks.origins[-1].meta_tick+2)
    if qualify:checks.require_weak()
    return checks


def accepted(checks,*,learn_count=2):
    for tick in (100,102):
        checks.pipeline.resolutions.append((tick,NS(pc=PC,branches=(NS(target=TARGET,position=POSITION,
            kind=Kind.DIRECT,taken=True,mispredict=True,action=StackAction.NONE),))))
    model = checks.pipeline.model.sources.micro
    for _ in range(learn_count):
        model.advance(UbtbEvents(fast_feedback=BranchTraining(PC*2,TARGET*2,1,POSITION,2,0,1)))
    model.advance(UbtbEvents())
    compared(checks,106)
    checks.burst_delivered((101,103))


def proof(checks,*,last=None):
    checks.last_source_tick = 110
    for index,hit in enumerate((True,True,True,False)):
        if last is not None and index>last:break
        source = public(checks,hit)
        checks.source(source,hit=hit,probe=True)
        learn(checks,False)
        compared(checks,source.meta_tick+2)


def test_complete_lifecycle_needs_real_source_identity_both_effects_and_distinguishing_probe():
    checks = weak()
    accepted(checks)
    assert checks.coverage.groups['checked'].coverage==60
    proof(checks)
    checks.finish()
    assert all(group.coverage==100 for group in checks.coverage.groups.values())


def test_independent_counter_algebra_distinguishes_a_lost_positive_update():
    checks = weak()
    assert checks.confidence()==1
    with pytest.raises(AssertionError,match='positive effects'):accepted(checks,learn_count=1)
    assert checks.confidence()==2
    assert 'rule.positive-effects-composed' in checks.coverage.groups['checked'].uncovered()


@pytest.mark.parametrize('fault',('pc','target','position','taken','s2','s3','meta-pc','meta-tick','source-tick'))
def test_bad_source_latches_without_resynchronizing_or_granting_probe_credit(fault):
    checks = weak()
    accepted(checks)
    checks.last_source_tick = 110
    source = public(checks,True)
    if fault=='pc':source.prediction.start_pc ^= 1
    elif fault=='target':source.prediction.target ^= 1
    elif fault=='position':source.prediction.position ^= 1
    elif fault=='taken':source.prediction.taken ^= 1
    elif fault=='s2':source.prediction.s2_override = 1
    elif fault=='s3':source.prediction.s3_override = 1
    elif fault=='meta-pc':source.meta.perf.start_pc ^= 1
    elif fault=='meta-tick':source.meta_tick += 2
    else:source.prediction_tick += 1
    state = deepcopy(checks.pipeline.model.sources.micro.state())
    with pytest.raises(AssertionError) as first:checks.source(source,hit=True,probe=True)
    with pytest.raises(AssertionError) as second:checks.source(public(checks,True),hit=True,probe=True)
    assert first.value is second.value and checks.pipeline.model.sources.micro.state()==state
    assert not checks.probes


@pytest.mark.parametrize('fault',('no-actual','wrong-owner','wrong-neighbor','stale-actual'))
def test_owned_weak_state_alone_is_not_a_qualified_precondition(fault):
    checks = weak(qualify=False)
    tick,actual = checks.pipeline.micro_checked
    if fault=='no-actual':checks.pipeline.micro_checked = None
    elif fault=='stale-actual':checks.pipeline.micro_checked = 0,actual
    else:
        values = list(actual)
        values[0 if fault=='wrong-owner' else 17] ^= 1
        checks.pipeline.micro_checked = tick,tuple(values)
    with pytest.raises(AssertionError):checks.require_weak()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('driver-gap','real-gap','missing','pc','target','position','kind','action','taken','mispredict'))
def test_nonadjacent_missing_or_wrong_actual_feedback_cannot_qualify_forwarding(fault):
    checks = weak()
    # Build a fully owned resulting state; corrupt only the claimed accepts.
    for _ in range(2):learn(checks,True)
    compared(checks,106)
    values = [NS(pc=PC,branches=(NS(target=TARGET,position=POSITION,kind=2,action=0,taken=True,mispredict=True),)) for _ in range(2)]
    ticks = (101,105) if fault=='driver-gap' else (101,103)
    checks.pipeline.resolutions.extend(((100,values[0]),(104 if fault=='real-gap' else 102,values[1])))
    if fault=='missing':checks.pipeline.resolutions.pop()
    elif fault=='pc':values[1].pc ^= 1
    elif fault not in ('driver-gap','real-gap'):
        value = getattr(values[1].branches[0],fault)
        setattr(values[1].branches[0],fault,value^1)
    with pytest.raises(AssertionError):checks.burst_delivered(ticks)
    assert checks.accepted is None
    assert 'rule.adjacent-same-owner-accepted' in checks.coverage.groups['checked'].uncovered()


@pytest.mark.parametrize('fault',('owner','neighbor','stale'))
def test_compared_effect_not_just_expected_three_is_required(fault):
    checks = weak()
    for _ in range(2):learn(checks,True)
    compared(checks,106)
    checks.pipeline.resolutions.extend((tick,NS(pc=PC,branches=(NS(target=TARGET,position=POSITION,
        kind=2,taken=True,mispredict=True,action=0),))) for tick in (100,102))
    tick,values = checks.pipeline.micro_checked
    actual = list(values)
    if fault=='stale':tick=100
    else:actual[0 if fault=='owner' else 21] ^= 1
    checks.pipeline.micro_checked = tick,tuple(actual)
    with pytest.raises(AssertionError):checks.burst_delivered((101,103))
    assert 'rule.positive-effects-composed' in checks.coverage.groups['checked'].uncovered()


@pytest.mark.parametrize('last',(0,1,2))
def test_early_termination_cannot_hide_one_lost_boost(last):
    checks = weak()
    accepted(checks)
    proof(checks,last=last)
    with pytest.raises(AssertionError):checks.finish()
    assert 'rule.depleted-after-three' in checks.coverage.groups['checked'].uncovered()


def test_missing_accept_and_reused_source_are_not_proof():
    checks = weak()
    source = public(checks,True)
    with pytest.raises(AssertionError,match='accepted adjacent'):checks.source(source,hit=True,probe=True)
    other = fixture()
    source = public(other,True)
    other.source(source,hit=True,origin=True)
    with pytest.raises(AssertionError,match='unique increasing'):other.source(source,hit=True,origin=True)


def test_case_has_no_signal_edge_get_set_or_asyncio_task_orchestration():
    for name in ('micro_capacity','micro_forwarding'):
        tree = ast.parse(Path(f'bpu/case/{name}.py').read_text())
        assert not any(isinstance(node,ast.ClassDef) for node in ast.walk(tree))
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                call = node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
                assert call not in {'ClockCycles','RisingEdge','FallingEdge','get_','set_','gather','create_task'}
    assert forwarding_coverage('checked').coverage==0
    with pytest.raises(AssertionError):MicroForwardingCoverage().finish()
