import ast
from pathlib import Path
from copy import deepcopy
import bpuverify.bpu.case.abtb.final_not_taken as production_scenario

SCENARIO = Path(production_scenario.__file__)
import pytest
from bpuverify.bpu.model.abtb.final_not_taken import nonzero_violations
from bpuverify.bpu.case.abtb.final_not_taken_plan import PILOT_CASES
from bpuverify.bpu.model.abtb.final_not_taken import PHASES
from bpuverify.bpu.model.abtb.final_not_taken import plan
from bpuverify.bpu.case.abtb.final_not_taken_plan import programs
from bpuverify.bpu.case.abtb.final_not_taken_plan import selected_program
from bpuverify.bpu.model.abtb.final_not_taken import capacity
from bpuverify.bpu.case.abtb.final_not_taken_plan import required_operations
from bpuverify.bpu.case.abtb.final_not_taken_plan import input_qualified
from bpuverify.bpu.case.abtb.final_not_taken_plan import final_comparison
from bpuverify.bpu.case.abtb.alias_plan import checkpoint_route


@pytest.mark.parametrize('bank,entry_set',PILOT_CASES)
def test_input_plan_is_real_fallthrough_and_capacity_safe(bank,entry_set):
    intent=plan(bank,entry_set)
    assert len(intent['cycles'])==5 and not nonzero_violations(intent['cycles'])
    assert max(capacity(intent['cycles']).values())<=2
    for alias in range(5):
        conditional,back,close,last=programs(intent,alias)
        negative=selected_program(intent,alias,0)
        assert negative['taken']==0 and negative['branch_type']==0
        assert negative['target']==conditional['target']==back['pc']
        assert back['target']==close['pc'] and close['target']==last['pc'] and last['target']==conditional['pc']
        assert negative['pc']==conditional['pc']
        for row in (conditional,back,close,last):
            assert checkpoint_route(row['pc'])['actual_not_taken_checkpoint_targets'][-1]==row['pc']-1


@pytest.mark.parametrize('bank,entry_set',PILOT_CASES)
@pytest.mark.parametrize('goal',[0,3])
def test_direction_expectation_is_from_intent_not_provider_output(bank,entry_set,goal):
    row=selected_program(plan(bank,entry_set),0,goal)
    assert row['taken']==int(bool(goal))
    assert row['branch_type']==(1 if goal else 0)
    assert row['position']==(6 if goal else 31)


@pytest.mark.parametrize('changed',['phase','bank','set_index','transition','feedback_pc','missing_feedback','feedback_taken'])
def test_negative_claim_requires_real_final_not_taken_not_later_taken(changed):
    intent=plan(0,0)
    phase='alias0_final_not_taken_to_zero'
    row=dict(phase=phase,bank=0,set_index=0,transition='dec0_0',
        feedback=dict(pc=intent['cycles'][0][0],taken=0))
    assert required_operations([row],intent,0,phase,('dec0_0',))['dec0_0']==[row]
    if changed=='feedback_pc':row['feedback']['pc']+=1
    elif changed=='feedback_taken':row['feedback']['taken']=1
    elif changed=='missing_feedback':row['feedback']=None
    elif changed in ('phase','transition'):row[changed]='wrong'
    else:row[changed]+=1
    assert required_operations([row],intent,0,phase,('dec0_0',))['dec0_0']==[]


def test_positive_claim_requires_real_taken_feedback():
    intent=plan(0,0)
    row=dict(phase='p',bank=0,set_index=0,transition='inc0_1',
        feedback=dict(pc=intent['cycles'][0][0],taken=1))
    assert required_operations([row],intent,0,'p',('inc0_1',))['inc0_1']==[row]
    row['feedback']['taken']=0
    assert not required_operations([row],intent,0,'p',('inc0_1',))['inc0_1']


def test_input_admission_does_not_require_provider_output():
    intent=plan(0,0)
    a,b,c,d=intent['cycles'][0]
    source=dict(prediction=dict(start_pc=a))
    token=dict(pc=d,bank=0,entry_set=0,mode='normal',folded6=intent['low4_index_source_history'])
    assert input_qualified(source,token,intent,0)
    assert not input_qualified(source,token,intent,1)
    for key in ('pc','bank','entry_set','folded6'):
        wrong=deepcopy(token)
        wrong[key]+=1
        assert not input_qualified(source,wrong,intent,0)
    wrong=dict(token,mode='S3_override')
    assert not input_qualified(source,wrong,intent,0)


def test_complete_final_comparison_distinguishes_taken_and_fallthrough():
    intent=plan(0,0)
    negative=selected_program(intent,0,0)
    source=dict(meta_tick=20)
    actual=dict(valid=1,pc=negative['pc'],taken=0,position=31,target=negative['target'],branch_type=0)
    rising=dict(tick=20,public_meta=dict(valid=1),abtb=dict(final=actual))
    expected,observed=final_comparison(negative,source,rising)
    assert expected==observed
    actual['taken']=1
    assert final_comparison(negative,source,rising)[0]!=final_comparison(negative,source,rising)[1]
    with pytest.raises(ValueError):final_comparison(negative,source,dict(rising,tick=21))


def test_all_eight_counter_transitions_are_required():
    assert {name for _,_,required in PHASES for name in required}=={
        'inc0_1','inc1_2','inc2_3','inc3_3','dec3_2','dec2_1','dec1_0','dec0_0'}


def test_prepare_and_feedback_never_install_a_later_fallback():
    tree=ast.parse(SCENARIO.read_text())
    feedback=[node for node in ast.walk(tree) if isinstance(node,ast.Call)
        and isinstance(node.func,ast.Name) and node.func.id=='BpuBranchFeedback']
    assert feedback
    for call in feedback:
        if len(call.args)>=3 and isinstance(call.args[0],ast.Constant) and call.args[0].value==7:
            assert isinstance(call.args[2],ast.Constant) and call.args[2].value==3
            raise AssertionError('unconditional edges must come from their own B/C program, not A fallback')
    assert not any(isinstance(node,ast.Name) and node.id=='fallback' for node in ast.walk(tree))


def test_scenario_does_not_override_checker_owned_context():
    import ast
    from pathlib import Path
    tree=ast.parse(SCENARIO.read_text())
    calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call)
        and isinstance(node.func,ast.Attribute) and node.func.attr=='compare']
    assert calls
    assert not [(node.lineno,kw.arg) for node in calls for kw in node.keywords
        if kw.arg in ('case','phase')]


def test_scenario_keeps_clock_and_pin_scheduling_inside_drivers():
    import ast
    from pathlib import Path
    tree=ast.parse(SCENARIO.read_text())
    forbidden={'FallingEdge','RisingEdge','ClockCycles','get_','set_','GetInternalSignal'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else (
                node.func.attr if isinstance(node.func,ast.Attribute) else '')
            assert name not in forbidden


@pytest.mark.parametrize('budget',[0,-1,True,1.5,65537])
def test_invalid_observation_budget_rejected(budget):
    from types import SimpleNamespace
    from bpuverify.bpu.checker.abtb.write import WriteChecker as BudgetedDirectChecks
    with pytest.raises(ValueError):BudgetedDirectChecks(SimpleNamespace(),max_frames=budget)


@pytest.mark.parametrize('budget',[1,20000,32768,65536])
def test_real_guard_still_fails_with_context_at_configured_limit(budget):
    from types import SimpleNamespace
    from toffee import ScoreboardMismatch
    from bpuverify.bpu.checker.abtb.write import WriteChecker as BudgetedDirectChecks
    checker=BudgetedDirectChecks(SimpleNamespace(),max_frames=budget)
    checker.records=[dict(tick=1)]*budget
    observation=SimpleNamespace(event=SimpleNamespace(tick=2),value={})
    with pytest.raises(ScoreboardMismatch) as caught:checker.observe('rising',observation)
    error=caught.value
    assert error.context.request['field']=='bounded_complete_observation'
    assert error.context.request['max_frames']==budget and error.context.request['frames']==budget
    assert error.context.observed_event.tick==2 and error.status.failed==1 and error.differences
    assert len(checker.records)==budget


def test_default_budget_preserves_original_behavior():
    from types import SimpleNamespace
    from bpuverify.bpu.checker.abtb.write import WriteChecker as BudgetedDirectChecks
    assert BudgetedDirectChecks(SimpleNamespace()).max_frames==20000


def test_current_A_admission_requires_two_beat_old_C_to_D_not_current_A_to_B():
    intent=plan(0,0)
    a,b,c,d=intent['cycles'][0]
    source=dict(prediction=dict(start_pc=a))
    token=dict(pc=d,bank=0,entry_set=0,mode='normal',folded6=intent['low4_index_source_history'])
    assert input_qualified(source,token,intent,0)
    assert not input_qualified(source,dict(token,pc=b),intent,0)
    assert not input_qualified(source,dict(token,pc=c),intent,0)
