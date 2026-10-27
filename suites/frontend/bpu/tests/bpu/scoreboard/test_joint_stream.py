"""Semantic wait invariants reject premature learning, bypass and fake progress."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
import ast
import json
import pytest
from toffee import Scoreboard,ScoreboardMismatch,CheckContext,ScoreboardMode
from bpuverify.bpu.model.joint_stream import Program,PROFILES,RULES,NEW_RULES
from bpuverify.bpu.model.joint_originals import RULES as ORIGINAL_RULES
from bpuverify.bpu.coverage.joint_stream import Coverage
from bpuverify.bpu.checker.joint_stream import Checks

pytestmark=pytest.mark.toffee_functional_coverage(False)


@pytest.mark.parametrize('profile',PROFILES)
def test_stream_keeps_the_existing_real_original_and_owned_read_view_semantics(profile):
    p=Program(profile)
    assert p.trained and p.truths[0] and p.iterations[1]==p.iterations[0]+1
    assert p.old_iteration>0 and p.fresh_counter in (6,7)
    assert p.state()['prediction_overlap'] and p.state()['whole_feedback_wait']
    assert not p.state()['serialized_shared_atomicity_required']
    assert not p.state()['fixed_wait_cycles'] and not p.state()['physical_enumeration']
    assert p.training_weights(p.iterations[0])!=p.training_weights(p.iterations[1])


@pytest.mark.parametrize('missing',RULES)
def test_old_pair_pass_or_any_partial_wait_cannot_award_whole_stream_credit(missing):
    c=Coverage(PROFILES[0])
    for rule in RULES:
        if rule!=missing:c.record(rule,1)
    with pytest.raises(AssertionError):c.finish()
    assert c.groups['checked'].coverage==0


def guard(profile):
    c=Checks.__new__(Checks);c.program=Program(profile)
    c.accepted_order=[];c.many=[dict(source=NS(sequence=i),accepted=None) for i in (1,2)]
    c.waiting=[];c.expected_patches=()
    c.actual_tage=[dict(valid=False) for _ in range(4)]
    c.observed=dict(statistical=dict(updates=[dict(valid=False) for _ in range(5)]))
    c.cycle=NS(fires=(True,False,False),next_pc=c.program.b)
    current=[dict(feedbacks=0,counter=6)]
    c.tage_learning_state=lambda:deepcopy(current[0])
    c.SC_learning_state=lambda:dict(weight=1)
    c.wait_before=c.tage_learning_state(),c.SC_learning_state()
    board=Scoreboard('joint-stream-negative-control')
    c.check=lambda expected,actual,point:board.check(expected=expected,actual=actual,
        context=CheckContext(board.name,ScoreboardMode.DIRECT,request=dict(point=point,profile=profile)))
    return c,current


@pytest.mark.parametrize('profile',PROFILES)
def test_actual_wait_receipt_requires_both_owners_and_nonlearning_models(profile):
    c,_=guard(profile);c.guard_waiting(10)
    assert len(c.waiting)==1 and c.waiting[0]['accepted']==(None,None)
    assert c.waiting[0]['both_learning_states_unchanged']


FAULTS=('accepted-head','tail-bypass','premature-direction-state','premature-correction-state',
    'native-direction-offer','native-correction-offer','hidden-correction-effect','no-prediction-progress','wrong-stream-PC')


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('fault',FAULTS)
def test_a_wait_cannot_hide_early_effects_or_rename_a_nonprogressing_trace(profile,fault):
    c,current=guard(profile)
    if fault=='accepted-head':c.accepted_order.append(1)
    elif fault=='tail-bypass':c.many[1]['accepted']=10
    elif fault=='premature-direction-state':current[0]['counter']=7
    elif fault=='premature-correction-state':c.SC_learning_state=lambda:dict(weight=2)
    elif fault=='native-direction-offer':c.actual_tage[0]['valid']=True
    elif fault=='native-correction-offer':c.observed['statistical']['updates'][0]['valid']=True
    elif fault=='hidden-correction-effect':c.expected_patches=((0,0,0,(1,)),)
    elif fault=='no-prediction-progress':c.cycle.fires=(False,False,False)
    else:c.cycle.next_pc+=16
    with pytest.raises(ScoreboardMismatch) as caught:c.guard_waiting(10)
    assert caught.value.context.request['point'] and not c.waiting


@pytest.mark.parametrize('profile',PROFILES)
def test_whole_new_contract_is_credited_only_for_this_complete_lifetime(profile):
    c=Coverage(profile)
    for rule in ORIGINAL_RULES:c.record(rule,1)
    with pytest.raises(AssertionError):c.finish()
    assert c.groups['checked'].coverage==0
    for rule in NEW_RULES:c.record(rule,2)
    c.finish()
    counts=c.groups['checked'].report()['points'][0]['counts']
    assert len(counts)==176 and {k for k,v in counts.items() if v}=={profile+'.'+r for r in RULES}


def test_contract_defines_behavior_and_reuses_the_existing_static_native_bundle():
    root=Path(__file__).resolve().parents[3]
    contract=json.loads((root/'docs/bpu-joint-stream-contract.json').read_text())
    assert tuple(contract['new_rules'])==NEW_RULES and contract['features']==['BPU-INT-107']
    assert len(PROFILES)==8 and len(RULES)==22
    case=ast.parse((root/'bpuverify/bpu/case/joint_stream.py').read_text())
    names={n.id for n in ast.walk(case) if isinstance(n,ast.Name)}|{n.attr for n in ast.walk(case) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','gather','create_task','sleep','set_','get'}
    env=(root/'bpuverify/bpu/env/joint_stream.py').read_text()
    assert 'lambda _:bool(c.waiting)' in env and 'admit_when' not in env


@pytest.mark.parametrize('proof_key',(7,41),ids=('owned-checkpoint','wrong-prediction-counter'))
def test_numeric_proof_uses_checkpoint_identity_not_an_equal_looking_prediction_sequence(proof_key):
    c,_=guard(PROFILES[0]);token=NS(sequence=41,history=NS(sequence=7))
    read=NS(indices=(1,2,3,4,5),weights=((1,),)*5)
    sources=NS(queries=NS(snapshot=lambda _:NS(loop=30,read=NS(valid=True))),statistical_snapshot=lambda _:NS(read=read))
    c.pipeline=NS(model=NS(sources=sources),sc_numeric_checked={proof_key:dict(read=8,consume=10,composition=10)})
    c.stream_consumers=[];c.numeric_stream_consumer(token,10)
    assert bool(c.stream_consumers)==(proof_key==7)
    if c.stream_consumers:assert (c.stream_consumers[0]['owner'],c.stream_consumers[0]['history_owner'])==(41,7)
