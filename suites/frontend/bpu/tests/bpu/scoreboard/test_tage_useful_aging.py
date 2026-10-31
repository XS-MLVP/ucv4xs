"""Independent truth tables and lifecycle rules; no DUT/native credit."""
from copy import deepcopy
from itertools import product
from types import SimpleNamespace
import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.bpu.checker.tage.aging import TageAgingChecker
from suites.frontend.bpu.bpu.coverage.tage.aging import AgingCoverage
from suites.frontend.bpu.bpu.model.tage.aging import empty_set,prediction,candidate_masks,transition,counter_transition,clear_step


@pytest.mark.parametrize('counter,fire,need,can,busy',tuple(product((0,1,254,255),(0,1),(0,1),(0,255),(0,1))))
def test_global_counter_reset_priority_and_qualified_accumulation(counter,fire,need,can,busy):
    after,start=counter_transition(counter,fire=fire,need=need,can=can,busy=busy)
    wanted_start=int(fire and counter==255 and not busy)
    wanted=0 if wanted_start else min(255,counter+int(fire and need and not can and not busy))
    assert (after,start)==(wanted,wanted_start)


@pytest.mark.parametrize('index,ready,start',tuple(product((0,1,510,511),(0,1),(0,1))))
def test_each_bank_uses_actual_write_acceptance_and_start_rewrites_zero(index,ready,start):
    before=[(1,index),(0,0)]
    after=clear_step(before,start=start,ready=[ready,ready])
    expected=(1,0) if start else (0,0) if ready and index==511 else (1,index+1) if ready else (1,index)
    assert after==[expected,(1,0) if start else (0,0)]


def test_candidate_priority_invalid_then_weak_unused_then_unused():
    cells=empty_set();meta=prediction(cells,0x40010008,4,3,(16,)*16)
    assert candidate_masks(cells,meta)==([3]*8,255)
    cells[0]=[dict(valid=1,tag=1,counter=3,useful=0),dict(valid=1,tag=2,counter=2,useful=0)]
    assert candidate_masks(cells,meta)[0][0]==1
    cells[0][0]['counter']=2
    assert candidate_masks(cells,meta)[0][0]==3
    cells[0][1]['valid']=0
    assert candidate_masks(cells,meta)[0][0]==2


@pytest.mark.parametrize('table,conf',tuple(product(range(8),(0,1))))
def test_highest_provider_and_selector_route_are_derived_from_known_tags(table,conf):
    cells=empty_set();pc=0x40010008;tag=((pc>>11)&8191)^4
    cells[table][1]=dict(valid=1,tag=tag,counter=3,useful=1)
    meta=prediction(cells,pc,4,3 if conf else 2,(16,)*16)
    assert (meta['hasProvider'],meta['providerTableIdx'],meta['providerWayIdx'],meta['altConf'],meta['useProvider'])==(1,table,1,conf,0)
    selectors=[16]*16;selectors[2*table+conf]=15
    assert prediction(cells,pc,4,3 if conf else 2,selectors)['useProvider']==1


def test_capacity_failures_do_not_modify_protected_entries_and_cleared_set_reopens():
    cells=[[dict(valid=1,tag=100+2*t+w,counter=2,useful=1) for w in range(2)] for t in range(8)]
    pc=0x40011008;meta=prediction(cells,pc,4,3,(16,)*16)
    result=transition(cells,meta,pc=pc,position=4,taken=0,mispredict=1,random_mask=0)
    assert (result['need'],result['can'],result['allocate'])==(1,0,0)
    assert result['after']==cells
    for table in cells:
        for cell in table:cell['useful']=0
    result=transition(cells,meta,pc=pc,position=4,taken=0,mispredict=1,random_mask=4)
    assert (result['allocate'],result['table'],result['way'])==(1,4,1)
    expected=deepcopy(cells);expected[2][0]=dict(valid=1,tag=((pc>>11)&8191)^4,counter=3,useful=0)
    assert result['after']==expected


def test_highest_provider_mispredict_is_not_an_allocation_failure_event():
    cells=empty_set();pc=0x40010008;cells[7][0]=dict(valid=1,tag=((pc>>11)&8191)^4,counter=2,useful=1)
    meta=prediction(cells,pc,4,3,(16,)*16)
    result=transition(cells,meta,pc=pc,position=4,taken=1,mispredict=1,random_mask=255)
    assert result['need']==result['allocate']==0


def empty_provider_public_source(base=3):
    checker=TageAgingChecker(AgingCoverage(),'demand');pc=0x40010008
    expected=prediction(checker.cells,pc,4,base,(16,)*16)
    owner=dict(rawHit=1,position=4,counter_value=base)
    resolved=dict(mbtb_entries=[[owner]],tage_entries=[expected])
    source=SimpleNamespace(prediction_tick=10,meta_tick=14,prediction=SimpleNamespace(start_pc=pc),
        meta=SimpleNamespace(resolve=resolved))
    fields=('hasProvider','providerTableIdx','providerWayIdx','providerTakenCtr_value','hasAlt','altConf','altOrBasePred','useProvider')
    checker.selector.records.append(dict(tick=12,expected_selectors=(16,)*16,
        prediction=dict(fire=1,pc=pc,slots=[dict(valid=0,taken=0,meta={key:expected[key] for key in fields})])))
    taken=int(base>=2)
    phr=SimpleNamespace(records=[dict(tick=14,parent=dict(s3_pc=pc,s3_target=0x40020180 if taken else (pc//16+2)*16,s3_taken=taken),
        boundary=dict(s3=dict(prediction=dict(position=4 if taken else 31))))])
    return checker,source,phr


def test_no_TAGE_provider_is_invalid_but_actual_final_base_is_taken():
    checker,source,phr=empty_provider_public_source()
    assert checker.public(source,0x40010008,4,0x40020180,phr)[1]==1


@pytest.mark.parametrize('base',range(4))
def test_base_fallback_preserves_complete_taken_or_fetch_end_prediction(base):
    checker,source,phr=empty_provider_public_source(base)
    assert checker.public(source,0x40010008,4,0x40020180,phr)[1]==int(base>=2)


@pytest.mark.parametrize('fault',('raw-valid','raw-meta','final-target','final-taken','final-source'))
def test_base_fallback_checks_raw_qualification_and_exact_final_source(fault):
    checker,source,phr=empty_provider_public_source()
    raw=checker.selector.records[0]['prediction']['slots'][0]
    if fault=='raw-valid':raw['valid']=1
    elif fault=='raw-meta':raw['meta']['hasProvider']=1
    elif fault=='final-target':phr.records[0]['parent']['s3_target']^=1
    elif fault=='final-taken':phr.records[0]['parent']['s3_taken']=0
    else:phr.records[0]['tick']+=2
    with pytest.raises(ScoreboardMismatch):checker.public(source,0x40010008,4,0x40020180,phr)


@pytest.mark.parametrize('data',(0,1))
def test_invalid_TAGE_data_is_not_an_alternate_prediction(data):
    checker,source,phr=empty_provider_public_source()
    checker.selector.records[0]['prediction']['slots'][0]['taken']=data
    assert checker.public(source,0x40010008,4,0x40020180,phr)[1]==1


def recovered_provider_public_source():
    checker,source,phr=empty_provider_public_source()
    checker.cells[0][0]=dict(valid=1,tag=36,counter=2,useful=0)
    checker.epochs=1;checker.restored_tag=36
    meta=prediction(checker.cells,0x40010008,4,3,(16,)*16)
    source.meta.resolve['tage_entries'][0]=meta
    raw=checker.selector.records[0]['prediction']['slots'][0]
    raw.update(valid=1,taken=0,meta={key:meta[key] for key in raw['meta']})
    phr.records[0]['parent'].update(s3_taken=0,s3_target=0x40010020)
    phr.records[0]['boundary']['s3']['prediction']['position']=31
    checker.allocation_effect=dict(tick=8,rule='allocation-restored',source=dict(accepted_tick=2))
    checker.sample('training','reached','allocation-restored')
    return checker,source,phr


def test_recovered_allocation_checked_credit_waits_for_complete_real_consumer():
    checker,source,phr=recovered_provider_public_source()
    assert checker.coverage.groups['training','checked'].samples==0
    checker.public(source,0x40010008,4,0x40020180,phr)
    assert checker.coverage.groups['training','checked'].samples==1
    assert checker.allocation_effect is None


def test_wrong_valid_TAGE_direction_preserves_reached_and_does_not_credit_allocation():
    checker,source,phr=recovered_provider_public_source()
    checker.selector.records[0]['prediction']['slots'][0]['taken']=1
    with pytest.raises(ScoreboardMismatch):checker.public(source,0x40010008,4,0x40020180,phr)
    assert checker.coverage.groups['training','reached'].samples==1
    assert checker.coverage.groups['training','checked'].samples==0
    assert checker.coverage.groups['consumer','checked'].samples==0


def source_row(checker,tx=None,fire=(0,0,0,0)):
    from tests.bpu.scoreboard.test_tage_selector import transaction,bits
    selector=dict(reset=0,selectors=list(checker.selector.values),enable=1,fire=fire,use_meta=1,
        raw_tags=[34]*8,reads=deepcopy(checker.cells),votes=[dict(valid=0,index=0,inc=0,dec=0) for _ in range(8)],
        training=dict(valid=int(tx is not None),ready=1,bits=bits(tx or transaction(valid=0))))
    tables=[]
    for t in range(8):
        banks=[]
        for b in range(4):
            active,index=checker.banks[t*4+b]
            banks.append(dict(busy=active,index=index,ports=[dict(valid=active,ready=1,address=index,data=0,enq=0,flush=0) for _ in range(2)]))
        tables.append(dict(busy=int(any(b['busy'] for b in banks)),start=0,banks=banks,staged_valid=0,
            staged_useful=[0,0],write=dict(valid=0,index=2,bank=1,way=0,entries=[])))
    age=dict(counter=checker.counter,busy=checker.busy,start=0,need=0,can=255,allocate=0,table=1,way=1,
        random=255,tables=tables,bank=1,sets=[2]*8,public_useful=[0]*10)
    return dict(selector=selector,age=age)


def qualified_failure(counter=254):
    from tests.bpu.scoreboard.test_tage_selector import transaction,bits
    checker=TageAgingChecker(AgingCoverage(),'demand')
    row=source_row(checker);row['selector']['reset']=1;checker.observe(row,10)
    checker.cells=[[dict(valid=1,tag=100+2*t+w,counter=2,useful=1) for w in range(2)] for t in range(8)]
    checker.counter=counter
    checker.observe(source_row(checker),12)
    meta=prediction(checker.cells,0x40011008,4,3,(16,)*16)
    tx=transaction(meta,taken=0,mispredict=1)
    tx.resolve_meta['mbtb_entries'][0][0]['counter_value']=3
    # The pure fixture names a distinct PC; no observed state or DUT is involved.
    from dataclasses import replace
    tx=replace(tx,pc=0x40011008)
    source=SimpleNamespace(prediction_tick=6,meta_tick=8,meta=SimpleNamespace(resolve=tx.resolve_meta))
    checker.plan(tx,source,enabled=True);checker.observe(source_row(checker,tx,fire=(1,1,0,0)),14)
    row=source_row(checker,fire=(0,0,1,0));row['selector']['use_meta']=0;checker.observe(row,16)
    row=source_row(checker,fire=(0,0,0,1));row['age'].update(need=1,can=0,allocate=0,table=0,way=0)
    row['selector']['votes'][0]=dict(valid=1,index=1,inc=0,dec=0)
    return checker,row


@pytest.mark.parametrize('fault',('missing-T3','wrong-demand','wrong-can','extra-allocation','missing-counter-effect'))
def test_failure_qualification_or_commit_error_preserves_reached_without_checked(fault):
    checker,row=qualified_failure()
    if fault=='missing-counter-effect':
        checker.observe(row,18);row=source_row(checker);row['age']['counter']=254;tick=20
    else:
        tick=18
        if fault=='missing-T3':row['selector']['fire']=(0,0,0,0)
        elif fault=='wrong-demand':row['age']['need']=0
        elif fault=='wrong-can':row['age']['can']=255
        else:row['age']['allocate']=1
    checker.capture(SimpleNamespace(value=row,event=SimpleNamespace(tick=tick)))
    with pytest.raises(ScoreboardMismatch):checker.raise_failure()
    assert checker.coverage.groups['training','reached'].samples==1
    assert checker.coverage.groups['training','checked'].samples==0


@pytest.mark.parametrize('fault',('missing-start','wrong-bank-state','wrong-address','wrong-zero-data','normal-enqueue'))
def test_clear_start_and_actual_bank_requests_fail_with_causal_state(fault):
    checker,row=qualified_failure(counter=255);row['age']['start']=1
    for table in row['age']['tables']:
        table['start']=1
        for bank in table['banks']:
            for port in bank['ports']:port.update(valid=1,flush=1)
    if fault=='missing-start':row['age']['start']=0;tick=18
    else:
        checker.observe(row,18);row=source_row(checker);tick=20
        bank=row['age']['tables'][0]['banks'][0];port=bank['ports'][1]
        if fault=='wrong-bank-state':bank['busy']=0
        elif fault=='wrong-address':port['address']=1
        elif fault=='wrong-zero-data':port['data']=1
        else:port['enq']=1
    checker.capture(SimpleNamespace(value=row,event=SimpleNamespace(tick=tick)))
    with pytest.raises(ScoreboardMismatch):checker.raise_failure()
    assert checker.coverage.groups['training','reached'].samples==1
    assert checker.coverage.groups['maintenance','checked'].samples==0
