"""Mutation controls are not hardware functional coverage."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.model.path_history import Checkpoint
from bpuverify.bpu.model.recovery_arbitration import RecoveryProgram
from bpuverify.bpu.checker.recovery_arbitration import RecoveryChecks,RULES

pytestmark=pytest.mark.toffee_functional_coverage(False)


@pytest.mark.parametrize('taken',(0,1))
@pytest.mark.parametrize('mode',('collision','after-repair'))
def test_recovery_expectation_uses_old_execution_not_either_younger_path(taken,mode):
    program=RecoveryProgram(taken,mode)
    assert program.winning_history==(2496 if taken else 0)
    assert program.expected_metadata==dict(phrPtr=dict(flag=taken,value=530 if taken else 0),
                                          phrLowBits=2496 if taken else 0)
    assert program.winning_history not in (1600,7232)


@pytest.mark.parametrize('fault',('bool-direction','unknown-mode'))
def test_invalid_semantic_program_cannot_be_silently_coerced(fault):
    with pytest.raises(ValueError):RecoveryProgram(True,'collision') if fault=='bool-direction' else RecoveryProgram(1,'queued')


def prepared(mode='collision'):
    program=RecoveryProgram(1,mode)
    checks=RecoveryChecks(program)
    checks.phase='arbitration'
    checks.pipeline=NS(current_event=NS(tick=100))
    checks.backend=NS(history=Checkpoint(5,0,0),sequence=4)
    events=NS(redirect=NS(source=checks.backend.history))
    token=NS(pc=program.pc,sequence=8,early=NS(branch=NS(taken=True)))
    young=NS(pc=program.micro_target,sequence=9)
    cycle=NS(tokens=(young,token,None),decisions=(None,NS(branch=NS(taken=False)),None),
             next_pc=program.target,middle_repair=mode=='collision',final_repair=False)
    model=NS(lookup_history=lambda *_:NS(history=program.winning_history))
    return program,checks,events,cycle,model


@pytest.mark.parametrize('fault',('none','wrong-owner','young-history','wrong-target','wrong-window','late-correction','wrong-middle-pc','wrong-middle-direction'))
def test_arbitration_input_and_competing_owner_are_independently_checked(fault):
    program,checks,events,cycle,model=prepared()
    if fault=='wrong-owner':events.redirect.source=replace(checks.backend.history)
    elif fault=='young-history':model.lookup_history=lambda *_:NS(history=1600)
    elif fault=='wrong-target':cycle.next_pc=program.pc+16
    elif fault=='wrong-window':cycle.middle_repair=False
    elif fault=='late-correction':cycle.final_repair=True
    elif fault=='wrong-middle-pc':cycle.tokens[1].pc+=16
    elif fault=='wrong-middle-direction':cycle.decisions[1].branch.taken=True
    if fault=='none':
        immediate,deferred=checks.candidates({},events,cycle,model,None,None)
        checks.reached(100,immediate,deferred)
        checks.checked(100,immediate,deferred)
        assert checks.pending==[(102,'backend-wins'),(102,'younger-cancelled')]
    else:
        with pytest.raises(AssertionError):checks.candidates({},events,cycle,model,None,None)
    assert checks.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('none','missing-successor','wrong-history','wrong-target','old-identity','middle-not-cancelled','wrong-tick'))
def test_real_next_boundary_must_cancel_old_work_and_present_only_backend_history(fault):
    program,checks,events,cycle,model=prepared()
    immediate,deferred=checks.candidates({},events,cycle,model,None,None)
    checks.reached(100,immediate,deferred)
    checks.checked(100,immediate,deferred)
    token=NS(pc=program.target,history=Checkpoint(12,program.winning_history,1),sequence=10)
    next_cycle=NS(tokens=(token,None,None))
    if fault=='missing-successor':next_cycle.tokens=(None,None,None)
    elif fault=='wrong-history':token.history=replace(token.history,history=7232)
    elif fault=='wrong-target':token.pc=program.micro_target
    elif fault=='old-identity':token.sequence=cycle.tokens[0].sequence
    elif fault=='middle-not-cancelled':next_cycle.tokens=(token,cycle.tokens[1],None)
    checks.frame=dict(cycle=next_cycle)
    if fault=='none':
        checks.checked(102,(),())
        assert set(checks.completions)=={'declared-arbitration-window','backend-wins','younger-cancelled'}
    else:
        with pytest.raises(AssertionError):checks.checked(104 if fault=='wrong-tick' else 102,(),())
    assert checks.groups['checked'].coverage==0


@pytest.mark.asyncio
async def test_gate_preserves_the_original_immutable_capture_not_later_live_checker_state():
    program,checks,events,cycle,model=prepared()
    checks.phase='setup'
    checks.arm()
    early=NS(tokens=(NS(pc=program.pc),None,None),fires=(True,True,False,False),
             decisions=(NS(branch=NS(taken=True)),None,None),flushes=(False,False,False),middle_repair=False)
    checks.frame=dict(cycle=early)
    checks.checked(90,(),())
    checks.frame=dict(cycle=cycle)
    checks.checked(92,(),())
    tick,snapshot=await checks.early_gate
    assert tick==90 and snapshot is early and snapshot is not checks.frame['cycle']
    assert (await checks.repair_gate)==(92,cycle)
    checks.disarm()


@pytest.mark.asyncio
async def test_armed_monitor_can_observe_an_empty_pipeline_without_inventing_a_successor():
    program,checks,events,cycle,model=prepared()
    checks.arm()
    checks.frame=dict(cycle=NS(tokens=(None,None,None),middle_repair=False))
    checks.checked(80,(),())
    assert not checks.early_gate.done() and not checks.repair_gate.done()
    checks.disarm()


@pytest.mark.parametrize('fault',('none','missing-obligation','old-metadata-mutated','old-failure'))
def test_checked_credit_requires_the_entire_semantic_lifetime_and_is_published_once(fault):
    program=RecoveryProgram(1,'collision')
    checks=RecoveryChecks(program)
    meta=dict(phr=dict(pointer=0))
    checks.frozen={'old':(NS(meta=meta),deepcopy(meta))}
    checks.consumer=dict(meta_tick=110)
    for rule in RULES[:-1]:
        checks.record('reached',rule,100)
        if fault!='missing-obligation' or rule!='fresh-history-consumer':checks.record('checked',rule,102)
    if fault=='old-metadata-mutated':meta['phr']['pointer']=1
    elif fault=='old-failure':
        with pytest.raises(AssertionError):checks.check(1,0,'a prior observed mismatch')
    assert checks.groups['checked'].coverage==0
    if fault=='none':
        checks.finish()
        assert checks.groups['checked'].coverage==25.0
        before=checks.groups['checked'].coverage
        with pytest.raises(AssertionError):checks.finish()
        assert checks.groups['checked'].coverage==before
    else:
        with pytest.raises(AssertionError):checks.finish()
        assert checks.groups['checked'].coverage==0
