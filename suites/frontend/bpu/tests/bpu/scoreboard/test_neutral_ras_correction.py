"""Missing/late/source/output controls cannot credit the neutral correction."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from toffee import ScoreboardMismatch
from bpuverify.bpu.case.ras.correction import correction_program
from bpuverify.bpu.checker.ras.correction import check_correction, check_program_output, check_wrong_path_absent
from bpuverify.bpu.checker.ras.micro import MicroRasChecker
from bpuverify.bpu.transaction.types import BpuPrediction, BpuStage1Source
from bpuverify.uras.model.pipeline import empty_state, advance


def witness(younger_action=2):
    plan, wrong = correction_program(younger_action)
    older, neutral = plan[2], plan[3]
    state = dict(empty_state(), s3_push=1, s3_address=older['pc']+16)
    inputs = dict(redirect=0,fire1=1,fire2=1,fire3=1,main_top=0x123,
        s1=dict(pc=wrong['pc'],position=wrong['position'],action=wrong['action']),
        s2=dict(valid=1,pc=neutral['pc'],position=neutral['position'],action=0),
        s3=dict(valid=0,pc=older['pc'],position=older['position'],action=2))
    after, route = advance(state,inputs)
    frame = dict(tick=43,inputs=inputs,expected_before=state,expected_after=after,route=route)
    public = dict(tick=43,public_prediction=dict(valid=1,bits=dict(start_pc=neutral['pc'],
        target=neutral['target'],taken=1,position=neutral['position'],s2_override=1,s3_override=0)),
        pipeline=dict(s1_flush=1),parent=dict(s3_pc=older['pc']))
    checker=MicroRasChecker();checker.records.append(frame)
    return checker,SimpleNamespace(records=[public]),SimpleNamespace(prediction_tick=41),older,neutral,wrong


def test_exact_neutral_correction_forwards_older_address_not_younger_call():
    values=witness();frame=check_correction(*values)
    assert frame['expected_after']['address']==values[3]['pc']+16
    assert frame['expected_after']['address']!=values[-1]['pc']+16


def test_exact_neutral_correction_preserves_older_push_and_vetoes_younger_return():
    values=witness(1);frame=check_correction(*values)
    assert frame['inputs']['s1']['action']==1
    assert frame['expected_after']['address']==values[3]['pc']+16
    assert frame['expected_after']['s2_pop']==0


FAULTS=('missing-frame','duplicate-frame','wrong-tick','route','redirect','s3-valid','s2-valid',
    's2-pc','s2-position','s2-action','fire2','s3-push','s3-pop','s3-address',
    's1-pc','s1-position','s1-action','fire1','after-usable','after-address','after-s2-push','after-s2-pop',
    'missing-public','duplicate-public','public-valid','no-flush','older-source',
    'public-start_pc','public-target','public-taken','public-position','public-s2_override','public-s3_override')


@pytest.mark.parametrize('fault',FAULTS)
def test_every_incorrect_or_missing_correction_ancestor_fails(fault):
    checker,phr,tx,older,neutral,wrong=witness()
    frame,public=checker.records[0],phr.records[0]
    if fault=='missing-frame':checker.records.clear()
    elif fault=='duplicate-frame':checker.records.append(deepcopy(frame))
    elif fault=='wrong-tick':frame['tick']+=2
    elif fault=='route':frame['route']='s1-call'
    elif fault in ('redirect','fire1','fire2'):frame['inputs'][fault]^=1
    elif fault in ('s3-valid','s2-valid'):
        frame['inputs'][fault[:2]]['valid']^=1
    elif fault.startswith(('s1-','s2-')):
        stage,key=fault.split('-');frame['inputs'][stage][key]^=1
    elif fault.startswith('s3-'):
        frame['expected_before']['s3_'+fault[3:]]^=1
    elif fault.startswith('after-'):
        key=fault[6:].replace('-','_');frame['expected_after'][key]^=1
    elif fault=='missing-public':phr.records.clear()
    elif fault=='duplicate-public':phr.records.append(deepcopy(public))
    elif fault=='public-valid':public['public_prediction']['valid']=0
    elif fault=='no-flush':public['pipeline']['s1_flush']=0
    elif fault=='older-source':public['parent']['s3_pc']^=1
    else:public['public_prediction']['bits'][fault[7:]]^=1
    with pytest.raises(ScoreboardMismatch):check_correction(checker,phr,tx,older,neutral,wrong)


def output_witness(cold=False):
    plan,_=correction_program();intent=plan[3] if cold else plan[0]
    prediction=BpuPrediction(intent['pc'],intent['pc']+16 if cold else intent['target'],
        int(not cold),intent['position'],0,0)
    tx=SimpleNamespace(prediction_tick=41,meta_tick=45,prediction=prediction,
        meta=SimpleNamespace(perf=SimpleNamespace(s1_source=BpuStage1Source.FALLTHROUGH if cold else BpuStage1Source.UBTB)))
    checker=MicroRasChecker();checker.records.append(dict(tick=41,inputs=dict(fire1=1,
        s1=dict(pc=intent['pc'],position=intent['position'],action=intent['action']))))
    phr=SimpleNamespace(records=[dict(tick=45,parent=dict(s3_pc=intent['pc'],s3_target=intent['target'],s3_taken=1),
        boundary=dict(s3=dict(prediction=dict(position=intent['position']))))])
    return checker,phr,tx,intent


@pytest.mark.parametrize('cold',(False,True))
def test_hot_early_and_cold_fallthrough_are_compared_to_same_final_program_intent(cold):
    check_program_output(*output_witness(cold),cold_neutral=cold)


OUTPUT_FAULTS=('source','missing-source','duplicate-source','input-fire1','input-pc','input-position','input-action',
    'missing-final','duplicate-final','final-pc','final-target','final-taken','final-position',
    'prediction-start_pc','prediction-target','prediction-taken','prediction-position','prediction-s2_override','prediction-s3_override')


@pytest.mark.parametrize('fault',OUTPUT_FAULTS)
def test_public_output_and_final_S3_cannot_be_reassociated_or_masked(fault):
    from dataclasses import replace
    checker,phr,tx,intent=output_witness(True)
    if fault=='source':tx.meta.perf.s1_source=BpuStage1Source.UBTB
    elif fault=='missing-source':checker.records.clear()
    elif fault=='duplicate-source':checker.records.append(deepcopy(checker.records[0]))
    elif fault=='input-fire1':checker.records[0]['inputs']['fire1']=0
    elif fault.startswith('input-'):checker.records[0]['inputs']['s1'][fault[6:]]^=1
    elif fault=='missing-final':phr.records.clear()
    elif fault=='duplicate-final':phr.records.append(deepcopy(phr.records[0]))
    elif fault=='final-position':phr.records[0]['boundary']['s3']['prediction']['position']^=1
    elif fault.startswith('final-'):phr.records[0]['parent']['s3_'+fault[6:]]^=1
    else:
        key=fault[11:];tx.prediction=replace(tx.prediction,**{key:getattr(tx.prediction,key)^1})
    with pytest.raises(ScoreboardMismatch):check_program_output(checker,phr,tx,intent,cold_neutral=True)


@pytest.mark.parametrize('channel',('public-meta','main-spec'))
def test_wrong_path_CALL_is_rejected_on_either_final_channel(channel):
    _,wrong=correction_program();checker=MicroRasChecker()
    phr=SimpleNamespace(records=[]);commit=SimpleNamespace(records=[])
    if channel=='public-meta':
        phr.records.append(dict(tick=45,public_meta=dict(valid=1,bits=dict(perf=dict(start_pc=wrong['pc'])))))
    else:commit.records.append(dict(tick=45,spec=dict(valid=1,pc_bytes=wrong['pc']*2)))
    with pytest.raises(ScoreboardMismatch,match='wrong-path operation'):
        check_wrong_path_absent(checker,phr,commit,wrong,41)


def test_genuine_preparation_of_sentinel_is_not_misclassified_as_later_wrong_path():
    _,wrong=correction_program();checker=MicroRasChecker()
    phr=SimpleNamespace(records=[dict(tick=39,public_meta=dict(valid=1,bits=dict(perf=dict(start_pc=wrong['pc']))))])
    commit=SimpleNamespace(records=[dict(tick=39,spec=dict(valid=1,pc_bytes=wrong['pc']*2))])
    check_wrong_path_absent(checker,phr,commit,wrong,41)


def test_program_has_one_semantic_wrong_path_sentinel_not_a_bank_matrix():
    plan,wrong=correction_program()
    assert len(plan)==7 and [r['action'] for r in plan]==[2,2,2,0,1,1,1]
    assert all(a['target']==b['pc'] for a,b in zip(plan,plan[1:]))
    assert wrong['pc']==plan[3]['pc']+16 and wrong['pc'] not in {r['pc'] for r in plan}
    assert wrong['action']==2 and wrong['pc']+16!=plan[2]['pc']+16


@pytest.mark.parametrize('action',(-1,0,3,True,'return'))
def test_invalid_younger_action_fails_before_DUT_access(action):
    with pytest.raises(ValueError):correction_program(action)
