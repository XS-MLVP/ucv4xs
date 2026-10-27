"""Owned semantic learning and synthetic adapter faults, not DUT coverage."""
import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.checker.main_learning import MainLearningChecks
from bpuverify.bpu.coverage.main_learning import MainLearningCoverage
from bpuverify.bpu.model.main_sources import BranchTargetSources,source_entries
from bpuverify.bpu.model.selection import Kind
from bpuverify.mbtb.model.semantic import Events,Feedback,Branch


PC,TARGET,POSITION = 0x40000800,0x40020800,5


def learned_frames():
    sources = BranchTargetSources()
    model = sources.main
    result = [model.lookup_snapshot(PC)]
    for taken in (True,False,True):
        feedback = Feedback((PC,PC+8),source_entries(result[-1]),
            (Branch(TARGET,taken,POSITION,1,mispredict=True),))
        model.advance(Events(feedback=feedback))
        for _ in range(8):model.advance()
        result.append(model.lookup_snapshot(PC))
    return tuple(result)


def token(frame,corrected=False):
    sources = BranchTargetSources()
    request = NS(pc=PC,lookup=frame)
    middle = sources.choose(request,2,(True,False,True,False,False,False,False))
    return NS(lookup=frame,middle=middle,middle_corrected=corrected)


def source(frame,tick,corrected):
    return NS(token=token(frame,corrected),prediction_tick=tick,meta_tick=tick+4,
        prediction=NS(start_pc=PC,taken=1,target=TARGET,position=POSITION))


def event(frame,tick,taken):
    return tick,NS(pc=PC,origin=token(frame),branches=(NS(position=POSITION,target=TARGET,
        kind=Kind.CONDITIONAL,taken=taken,mispredict=True,action=0),))


def fixture():
    coverage = MainLearningCoverage()
    pipeline = NS(raise_failure=lambda:None,source_token=lambda value:value.token)
    checks = MainLearningChecks(pipeline,PC,TARGET,POSITION,coverage)
    return checks,learned_frames()


def first_effect(checks,frames):
    checks.accepted(event(frames[0],10,True),True)
    checks.observed(source(frames[1],12,False),2,False)


def test_complete_owned_lifecycle_has_no_coverage_until_actual_accept_and_effect():
    checks,frames = fixture()
    assert all(group.coverage==0 for group in checks.coverage.groups.values())
    checks.accepted(event(frames[0],10,True),True)
    assert checks.coverage.groups['reached'].coverage==40 and checks.coverage.groups['checked'].coverage==0
    checks.observed(source(frames[1],12,False),2,False)
    checks.accepted(event(frames[1],20,False),False)
    checks.observed(source(frames[2],22,True),1,True)
    checks.accepted(event(frames[2],30,True),True)
    checks.observed(source(frames[3],32,False),2,False)
    checks.finish()
    assert all(group.coverage==100 for group in checks.coverage.groups.values())


@pytest.mark.parametrize('field',('pc','position','target','kind','taken','mispredict','action','origin'))
def test_wrong_actual_accepted_outcome_never_receives_checked_credit(field):
    checks,frames = fixture()
    actual = event(frames[0],10,True)
    resolution = actual[1]
    if field=='origin':resolution.origin=None
    elif field=='pc':resolution.pc ^= 1
    else:setattr(resolution.branches[0],field,getattr(resolution.branches[0],field)^1)
    with pytest.raises(AssertionError) as first:checks.accepted(actual,True)
    with pytest.raises(AssertionError) as second:checks.accepted(event(frames[0],12,True),True)
    assert first.value is second.value and checks.pending is None
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('field',('pc','target','taken','position','repair','middle-direction','middle-target'))
def test_bad_effect_or_consumer_cannot_close_an_accepted_event(field):
    checks,frames = fixture()
    checks.accepted(event(frames[0],10,True),True)
    actual = source(frames[1],12,False)
    if field=='repair':actual.token.middle_corrected=True
    elif field=='middle-direction':actual.token.middle = replace(actual.token.middle,
        branch=replace(actual.token.middle.branch,taken=False))
    elif field=='middle-target':actual.token.middle = replace(actual.token.middle,
        branch=replace(actual.token.middle.branch,target=TARGET+16))
    else:setattr(actual.prediction,'start_pc' if field=='pc' else field,
        getattr(actual.prediction,'start_pc' if field=='pc' else field)^1)
    with pytest.raises(AssertionError):checks.observed(actual,2,False)
    assert checks.pending is not None and not checks.transitions
    assert checks.coverage.groups['checked'].coverage==0


def test_same_pc_cold_metadata_cannot_be_reused_for_a_learned_counter_update():
    checks,frames = fixture()
    first_effect(checks,frames)
    with pytest.raises(AssertionError,match='expected logical branch'):
        checks.accepted(event(frames[0],20,False),False)
    assert checks.coverage.groups['checked'].coverage==40


def test_a_changed_physical_owner_cannot_look_like_same_branch_recovery():
    checks,frames = fixture()
    first_effect(checks,frames)
    checks.accepted(event(frames[1],20,False),False)
    frame = frames[2]
    bank = frame.banks[0]
    moved = replace(bank,entries=tuple(reversed(bank.entries)),counters=tuple(reversed(bank.counters)))
    wrong = replace(frame,banks=(moved,frame.banks[1]))
    with pytest.raises(AssertionError):checks.observed(source(wrong,22,True),1,True)
    assert checks.coverage.groups['checked'].coverage==40


def test_same_counter_from_another_owner_cannot_qualify_an_accepted_update():
    checks,frames = fixture()
    first_effect(checks,frames)
    frame = frames[1]
    bank = frame.banks[0]
    moved = replace(bank,entries=tuple(reversed(bank.entries)),counters=tuple(reversed(bank.counters)))
    wrong = replace(frame,banks=(moved,frame.banks[1]))
    with pytest.raises(AssertionError,match='original physical owner'):
        checks.accepted(event(wrong,20,False),False)
    assert checks.pending is None and checks.coverage.groups['reached'].coverage==40


def test_early_end_or_unplanned_effect_cannot_pass():
    checks,frames = fixture()
    with pytest.raises(AssertionError):checks.observed(source(frames[1],12,False),2,False)
    other,frames = fixture()
    first_effect(other,frames)
    with pytest.raises(AssertionError):other.finish()


def test_scenario_keeps_checking_and_signal_timing_out_of_the_case():
    tree = ast.parse(Path('bpuverify/bpu/case/main_learning.py').read_text())
    for node in ast.walk(tree):
        assert not isinstance(node,(ast.ClassDef,ast.Assert))
        if isinstance(node,ast.Call):
            name = node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in {'ClockCycles','RisingEdge','FallingEdge','get_','set_','gather','create_task','Scoreboard'}
