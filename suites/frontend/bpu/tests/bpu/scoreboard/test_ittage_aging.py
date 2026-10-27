"""No-DUT independent tick/priority/source/effect contracts; no native credit."""
from itertools import product
from types import SimpleNamespace
from dataclasses import asdict
from copy import deepcopy
import pytest
from toffee import ScoreboardMismatch
from bpuverify.bpu.model.ittage_aging import SETS,BANKS,MAX_TICK,ENTRY_MASK,USEFUL_MASK,tick_step,table_step,write_plan
from bpuverify.bpu.coverage.ittage_aging import AgingCoverage,RULES
from bpuverify.bpu.checker.ittage_aging import IttageAgingChecker
from bpuverify.bpu.model.sc.model import canonical,encoded_payload
from bpuverify.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback


def tx(*,allocate=False,mispredict=1,counter=2,correct=False):
    meta=dict(provider=dict(valid=1,bits=2),providerCnt_value=counter,providerTarget_addr=42,
        providerUsefulCnt_value=1,altProvider=dict(valid=1,bits=0),altProviderCnt_value=2,
        altProviderTarget_addr=40,altDiffers=1,allocate=dict(valid=int(allocate),bits=1))
    return BpuBatchTraining(0x40000806,dict(ittage=meta),
        (BpuBranchFeedback(7,42 if correct else 43,3,taken=1,mispredict=mispredict),))


@pytest.mark.parametrize('before,allocate,mispredict,unconfident,correct',tuple(product((0,1,254,255),(False,True),(0,1),(False,True),(False,True))))
def test_tick_qualification_and_automatic_reset_priority(before,allocate,mispredict,unconfident,correct):
    value=canonical(asdict(tx(allocate=allocate,mispredict=mispredict,counter=0 if unconfident else 2,correct=correct)))
    after,rule=tick_step(before,value)
    if before==255:assert (after,rule)==(0,'saturation-reset')
    elif not mispredict or (unconfident and correct):
        assert after==before
        assert rule==('correct-unconfident-suppressed' if mispredict else 'correct-update-suppressed')
    else:assert (after,rule)==(max(0,before-1),'decrement') if allocate else (before+1,'increment')


@pytest.mark.parametrize('sets,busy,last,predict,update,start',tuple(product(sorted(set(SETS)),(0,1),(False,True),(False,True),(False,True),(False,True))))
def test_each_geometry_advances_only_on_quiet_cycles_with_start_priority(sets,busy,last,predict,update,start):
    index=sets-1 if last else 0
    after,cursor=table_step(busy,index,request=predict,update=update,start=start,sets=sets)
    step=bool(busy and not predict and not update)
    assert cursor==(index+int(step))%sets
    assert after==int(bool(start or (busy and not(last and step))))


def row(checker,*,reset=0,feedback=None):
    stage=dict(valid=int(checker.t1 is not None),pc=0,provider=0,counter=0,target=0,allocate=0,
        branches=[dict(valid=0,target=0,taken=0,kind=0,mispredict=0) for _ in range(8)])
    if checker.t1 is not None:
        value=checker.t1['value'];meta=value['resolve_meta']['ittage'];branch,=value['branches']
        stage.update(pc=value['pc'],provider=meta['provider']['valid'],counter=meta['providerCnt_value'],
            target=meta['providerTarget_addr'],allocate=meta['allocate']['valid'])
        stage['branches'][0]=dict(valid=1,target=branch['target'],taken=1,kind=3,mispredict=branch['mispredict'])
    tables=[]
    for t,(busy,index) in enumerate(checker.tables):
        normal=checker.normal[t];advance=int(bool(busy and normal is None))
        banks=[]
        for b in range(BANKS):
            active=bool(normal is not None and normal['pc']&1==b)
            enqueue=dict(valid=int(advance or active),index=index if advance else
                ((normal['pc']>>1)&(SETS[t]-1)) if active else 0,
                mask=USEFUL_MASK if advance else (ENTRY_MASK if normal['useful_valid'] else ENTRY_MASK^USEFUL_MASK) if active else 0,
                useful=0 if advance else normal['useful'] if active else 0)
            banks.append(dict(enqueue=enqueue,ram=dict(valid=advance,ready=1,index=index,mask=2 if advance else 0,useful=0)))
        tables.append(dict(busy=busy,index=index,advance=advance,start=checker.pulse,
            request=dict(valid=0,ready=1),update=dict(valid=int(normal is not None),**(normal or {})),
            banks=banks))
    return dict(reset=reset,enable=1,counter=checker.counter,stage=stage,tables=tables,
        feedback_valid=int(feedback is not None),feedback_ready=1,
        feedback=None if feedback is None else encoded_payload(canonical(asdict(feedback))))


def observe(checker,phase,value,tick):
    checker.observe(phase,SimpleNamespace(value=value,event=SimpleNamespace(tick=tick)))


def cycle(checker,tick,*,feedback=None,reset=0):
    observe(checker,'preedge',row(checker,reset=reset,feedback=feedback),tick)
    effect=checker.next;rising=row(checker,reset=reset)
    rising['counter']=effect['counter']
    for i,t in enumerate(rising['tables']):t['busy'],t['index']=effect['tables'][i];t['start']=effect['pulse']
    observe(checker,'rising',rising,tick+1)


def pending_effect():
    checker=IttageAgingChecker(AgingCoverage());cycle(checker,10,reset=1)
    value=tx();source=SimpleNamespace(prediction_tick=4,meta_tick=6,
        prediction=SimpleNamespace(start_pc=value.pc),meta=SimpleNamespace(resolve=value.resolve_meta))
    checker.plan(value,source);cycle(checker,12,feedback=value)
    return checker


def test_actual_source_T1_then_next_counter_commit_is_not_input_presentation():
    checker=pending_effect()
    assert checker.counter==0 and checker.coverage.groups['training','reached'].samples==0
    cycle(checker,14)
    assert checker.counter==1 and checker.coverage.groups['training','checked'].samples==1
    cycle(checker,16);cycle(checker,18)
    summary=checker.summary();assert summary['counts']['accepted']==1
    witness=next(iter(checker.coverage.groups['training','checked'].report()['points'][0]['provenance']['increment'].values()))['first']
    assert (witness['prediction_tick'],witness['meta_tick'],witness['accepted_tick'],witness['T1_tick'],witness['committed_tick'])==(4,6,12,14,15)


@pytest.mark.parametrize('fault',('T1-valid','source-PC','provider-counter','provider-target','allocation',
    'branch-target','branch-valid','counter-effect','cursor-effect','reset-pulse','lost-observation'))
def test_source_or_commit_fault_retains_reached_without_checked(fault):
    checker=pending_effect();value=row(checker);phase='preedge';tick=14
    if fault.endswith('effect') or fault in ('reset-pulse','lost-observation'):
        observe(checker,phase,value,tick);effect=checker.next;value=row(checker)
        value['counter']=effect['counter'];phase='rising';tick=15
        if fault=='counter-effect':value['counter']=0
        elif fault=='cursor-effect':value['tables'][0]['index']=1
        elif fault=='reset-pulse':value['tables'][0]['start']=1
        else:tick+=2
    elif fault=='T1-valid':value['stage']['valid']=0
    elif fault=='source-PC':value['stage']['pc']+=8
    elif fault=='provider-counter':value['stage']['counter']^=1
    elif fault=='provider-target':value['stage']['target']^=1
    elif fault=='allocation':value['stage']['allocate']=1
    elif fault=='branch-target':value['stage']['branches'][0]['target']^=1
    else:value['stage']['branches'][1]['valid']=1
    checker.capture(phase,SimpleNamespace(value=value,event=SimpleNamespace(tick=tick)))
    with pytest.raises(ScoreboardMismatch):checker.raise_failure()
    assert checker.coverage.groups['training','reached'].samples==1
    assert checker.coverage.groups['training','checked'].samples==0


@pytest.mark.parametrize('family,status,missing',[(family,status,rule) for family,rules in RULES.items()
    for status in ('reached','checked') for rule in rules])
def test_each_event_requirement_is_mandatory_without_stage_or_bank_axes(family,status,missing):
    group=AgingCoverage().groups[family,status]
    for rule in RULES[family]:
        if rule!=missing:group.sample(dict(rule=rule))
    with pytest.raises(AssertionError):group.assert_coverage(100)
    assert tuple(p.name for p in group.definition.points)==('rule',) and not group.definition.crosses


def normal_alternate_checker():
    checker=IttageAgingChecker(AgingCoverage());cycle(checker,10,reset=1)
    value=tx(counter=0)
    source=SimpleNamespace(prediction_tick=4,meta_tick=6,
        prediction=SimpleNamespace(start_pc=value.pc),meta=SimpleNamespace(resolve=value.resolve_meta))
    checker.plan(value,source);cycle(checker,12,feedback=value);cycle(checker,14)
    assert checker.normal[0]['useful_valid']==0
    return checker


def test_masked_alternate_useful_payload_is_not_a_defined_write_operand():
    checker=normal_alternate_checker();value=row(checker)
    value['tables'][0]['update']['useful']=1
    value['tables'][0]['banks'][0]['enqueue']['useful']=1
    observe(checker,'preedge',value,16)
    assert checker.board.status.failed==0


@pytest.mark.parametrize('fault',('useful-mask','neighbor-bank','wrong-address','provider-useful'))
def test_actual_normal_write_mask_bank_address_and_enabled_useful_remain_checked(fault):
    checker=normal_alternate_checker();value=row(checker)
    if fault=='useful-mask':value['tables'][0]['banks'][0]['enqueue']['mask']|=USEFUL_MASK
    elif fault=='neighbor-bank':value['tables'][0]['banks'][1]['enqueue']['valid']=1
    elif fault=='wrong-address':value['tables'][0]['banks'][0]['enqueue']['index']^=1
    else:value['tables'][2]['banks'][0]['enqueue']['useful']^=1
    with pytest.raises(ScoreboardMismatch):observe(checker,'preedge',value,16)


def test_saturation_needs_no_extra_feedback_and_all_geometries_reach_actual_zero_write_footprint():
    checker=IttageAgingChecker(AgingCoverage());cycle(checker,10,reset=1);tick=12
    for _ in range(MAX_TICK):
        value=tx();source=SimpleNamespace(prediction_tick=tick-8,meta_tick=tick-6,
            prediction=SimpleNamespace(start_pc=value.pc),meta=SimpleNamespace(resolve=value.resolve_meta))
        checker.plan(value,source);cycle(checker,tick,feedback=value);cycle(checker,tick+2);tick+=4
    assert checker.counter==255 and checker.counts['epochs']==0
    cycle(checker,tick);tick+=2
    assert checker.counter==0 and checker.pulse==1 and checker.counts['epochs']==1
    cycle(checker,tick);tick+=2
    assert checker.tables==[(1,0)]*3
    for _ in range(max(SETS)):
        cycle(checker,tick);tick+=2
    checker.finish_maintenance()
    assert checker.tables==[(0,0)]*3 and checker.counts['clear_write_accepts']==2*sum(SETS)==1024
    assert checker.coverage.groups['maintenance','checked'].report()['points'][0]['counts']['sweep-completed']==1
