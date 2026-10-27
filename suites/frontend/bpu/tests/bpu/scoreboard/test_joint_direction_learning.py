"""No-DUT obligations and negative controls for independent joint effects."""
from copy import deepcopy
from dataclasses import replace
import ast
from pathlib import Path
import pytest
from bpuverify.bpu.model.joint_direction_learning import Program,PROFILES,RULES,tage_offer_values
from bpuverify.bpu.coverage.joint_direction_learning import Coverage
from bpuverify.tage.model.semantic import TageReference,Events as TageEvents,Feedback,Branch,Hint,Context as TageContext,Write,Entry
from bpuverify.sc.model.semantic import ScReference,Events,Context,decide
from bpuverify.sc.transaction.types import ScHistory,ScBaseBranch,ScBatchTraining,ScBranchFeedback

pytestmark=pytest.mark.toffee_functional_coverage(False)


@pytest.mark.parametrize('profile',PROFILES)
def test_strongest_direction_confidence_and_one_error_determine_teaching_not_cycles(profile):
    p=Program(profile)
    assert p.teaching_count==8 and 5*(2*(p.teaching_count-1)+1)>1130//16
    assert 5*(2*(p.teaching_count-2)+1)<=1130//16
    assert p.state()['core_original_counters']==(5,6,7)
    assert p.old_iteration>0 and p.young_iteration>p.old_iteration
    assert not p.state()['physical_enumeration']


@pytest.mark.parametrize('profile',PROFILES)
def test_joint_original_reserves_a_real_history_window_for_registered_observation(profile):
    p=Program(profile)
    assert p.young_iteration-p.old_iteration==2
    assert p.require_feedback_window(110,100)==20
    for current in (99,111,200):
        with pytest.raises(ValueError,match='retained history window'):p.require_feedback_window(current,100)


def lookup(m,p,history,counter):
    return decide(
        m.snapshot(p.b,Context.from_history(history)),
        (ScBaseBranch(p.position,counter),*(ScBaseBranch(i,0,0,0,0) for i in (0,2,3))),m.thresholds.values)


def drain(m):
    for _ in range(16):
        if m.learning is None and not m.pending and not any(v is not None and v.dirty for banks in m.writes for c in banks for v in c.rows):return
        m.advance()
    raise AssertionError('independent semantic learning failed to drain')


@pytest.mark.parametrize('profile',PROFILES)
def test_same_original_qualification_survives_changing_TAGE_confidence(profile):
    p=Program(profile);m=ScReference();old=ScHistory(0x93,255,15,p.old_iteration)
    originals=[lookup(m,p,old,5) for _ in range(p.teaching_count)]
    def send(source,taken):
        tx=ScBatchTraining(p.b,source.metadata(),(ScBranchFeedback(p.position,int(taken),0),),old)
        m.advance(Events(feedback=tx,feedback_context=Context.from_history(old)));drain(m)
    send(originals[0],True)
    after_cold=lookup(m,p,old,6)
    assert after_cold.used[0]==0
    for source in originals[1:]:send(source,True)
    strong=lookup(m,p,old,6);assert strong.used[0]==1
    before=deepcopy(m.memory),m.thresholds.values
    send(strong,True)
    assert before==(m.memory,m.thresholds.values)
    correct=lookup(m,p,old,7);assert correct.used[0]==1
    young=replace(old,loop=p.young_iteration)
    private_before=lookup(m,p,young,7).read.weights[3]
    send(correct,False)
    wrong=lookup(m,p,old,6);assert wrong.used[0]==wrong.directions[0]==1
    assert all(a!=b for a,b in zip(correct.read.weights,wrong.read.weights,strict=True))
    assert private_before==lookup(m,p,young,6).read.weights[3]


@pytest.mark.parametrize('counter',range(8))
@pytest.mark.parametrize('taken',(False,True))
def test_TAGE_preview_is_pure_and_equals_the_next_owned_schedule(counter,taken):
    m=TageReference();hint=Hint(provider=True,use_provider=True,table=3,counter=counter)
    tx=Feedback(0x4000,TageContext(),(Branch(1,taken,1,False,True,hint=hint),))
    m.advance(TageEvents(feedback=tx));m.advance();m.advance()
    before=deepcopy(m.state())
    before_cache=deepcopy(tuple((c.records,c.pending,c.recency) for c in m.cache.values()))
    writes,useful,start=m.preview_learning()
    assert m.state()==before and tuple((c.records,c.pending,c.recency) for c in m.cache.values())==before_cache
    assert (writes,useful,start)==m.preview_learning()
    m.advance()
    assert {key[:2]+(v.way,):v for key,values in m.offers.items() for v in values}==writes
    assert m.useful_offers==useful


def actual_offer():
    blank=lambda:dict(valid=0,index=0,bank=0,ways=0,entry_mask=(0,0),useful_mask=(0,0),taken=(0,0),
        entries=[dict(valid=0,tag=0,counter=0) for _ in range(2)],useful=(0,0))
    rows=[blank() for _ in range(4)]
    rows[3].update(valid=1,index=4,bank=1,ways=1,entry_mask=(1,0),taken=(1,0),entries=[dict(valid=1,tag=17,counter=6),dict(valid=0,tag=0,counter=0)])
    writes={(3,0,0):Write(4,0,Entry(True,17,6),True)}
    return writes,rows


@pytest.mark.parametrize('fault',('valid','index','bank','ways','entry_mask','useful_mask','taken','entry-valid','tag','counter','other-table'))
def test_complete_TAGE_offer_projection_detects_each_defined_fault(fault):
    writes,rows=actual_offer();e,a=tage_offer_values(writes,{},rows);assert e==a
    row=rows[3]
    if fault in ('valid','index','bank','ways'):row[fault]^=1
    elif fault in ('entry_mask','useful_mask','taken'):row[fault]=tuple(1-v for v in row[fault])
    elif fault=='other-table':rows[0]['valid']=1
    else:row['entries'][0][{'entry-valid':'valid','tag':'tag','counter':'counter'}[fault]]^=1
    e,a=tage_offer_values(writes,{},rows);assert e!=a


def test_unwritten_TAGE_payload_is_not_required_to_be_zero():
    writes,rows=actual_offer();rows[0]['index']=73;rows[3]['entries'][1]['counter']=7
    e,a=tage_offer_values(writes,{},rows);assert e==a


@pytest.mark.parametrize('count',(0,3,5))
def test_no_table_can_be_silently_omitted_from_actual_offer_comparison(count):
    _,rows=actual_offer()
    with pytest.raises(ValueError,match='all four'):tage_offer_values({}, {},(rows*2)[:count])


def test_committed_memory_direct_layout_has_every_new_read_only_TAGE_port():
    import yaml
    from bpuverify.bpu.bundle.tage_semantic import HISTORY_PORTS
    root=Path(__file__).resolve().parents[3]
    layout=yaml.load((root/'dut/bpu/BpuDut_offset.yaml').read_bytes(),Loader=yaml.CSafeLoader)
    names={r['name'] for field in ('variables','signals') for r in layout.get(field,())}
    anchor,=[n for n in names if n.endswith('.tage.io_enable')]
    prefix=anchor.removesuffix('tage.io_enable')
    fields=['valid','bits_setIdx','bits_bankMask','bits_wayMask']
    for w in range(2):
        fields += [f'bits_{kind}_{w}' for kind in ('writeEntryEn','writeUsefulEn','actualTakenMask')]
        fields += [f'bits_entries_{w}_{f}' for f in ('valid','tag','takenCtr_value')]
        fields += [f'bits_usefulCtrs_{w}_value']
    assert {prefix+f'tage.tables_{t}.io_writeReq_'+f for t in range(4) for f in fields}<=names
    assert {prefix+f'tage.io_fromPhr_foldedPathHistForTrain_hist_{i}_foldedHist' for i in HISTORY_PORTS}<=names


@pytest.mark.parametrize('missing',RULES)
def test_every_joint_obligation_is_required_before_checked_credit(missing):
    c=Coverage(PROFILES[0])
    for rule in RULES:
        if rule!=missing:c.record(rule,10)
    with pytest.raises(AssertionError):c.finish()
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
def test_completed_program_only_awards_its_own_joint_obligations(profile):
    c=Coverage(profile)
    for rule in RULES:c.record(rule,10)
    c.finish()
    counts=c.groups['checked'].report()['points'][0]['counts']
    assert len(counts)==64 and {k for k,v in counts.items() if v}=={profile+'.'+r for r in RULES}


def test_new_case_uses_semantic_operations_not_clock_edges_or_raw_IO():
    import json
    path=Path(__file__).resolve().parents[3]/'bpuverify/bpu/case/joint_direction_learning.py'
    tree=ast.parse(path.read_text())
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}|{n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    assert not names&{'FallingEdge','RisingEdge','ClockCycles','gather','create_task','sleep','set_','get'}
    root=Path(__file__).resolve().parents[3]
    contract=json.loads((root/'docs/bpu-joint-direction-learning-contract.json').read_text())
    point=next(r for r in json.loads((root/'verification_plan.json').read_text())['features'] if r['id']==contract['feature'])
    assert point['contract']=={k:contract[k] for k in ('event','owner','effect','observation','preservation','scope')}
    assert point['metadata']['semantic_requirements']==contract['program']
