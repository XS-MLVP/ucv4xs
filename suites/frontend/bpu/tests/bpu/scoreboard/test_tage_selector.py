"""Pure qualifier, source, saturation and fault contracts; no native credit."""
from copy import deepcopy
from dataclasses import asdict,replace
from itertools import product
from types import SimpleNamespace
import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.bpu.model.tage.selector import feedback_votes,update_selectors,read_projection,exercise_program
from suites.frontend.bpu.bpu.checker.tage.selector import TageSelectorChecker
from suites.frontend.bpu.bpu.coverage.tage.selector import SelectorCoverage
from suites.frontend.bpu.bpu.model.sc.model import encoded_payload,canonical
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback
from suites.frontend.bpu.tage.model.pair import TagePairModel


def metadata(counter=4,alt=0,table=7,conf=1,**options):
    return dict(hasProvider=1,providerTableIdx=table,providerWayIdx=0,
        providerTakenCtr_value=counter,providerUsefulCtr_value=0,hasAlt=0,
        altOrBasePred=alt,altConf=conf,useProvider=0,**options)


def transaction(meta=None,*,taken=0,owner=1,conditional=1,valid=1,mispredict=0):
    entry=dict(rawHit=owner,position=4,counter_value=0)
    miss=dict(rawHit=0,position=0,counter_value=0)
    resolved=dict(mbtb_entries=[[entry,miss,miss,miss,miss],[miss]*5],tage_entries=[meta or metadata()]+[metadata() for _ in range(9)])
    tx=BpuBatchTraining(0x40010008,resolved,(BpuBranchFeedback(4,0x40020080,
        1 if conditional else 3,taken=taken,mispredict=mispredict),) if valid else (None,))
    return tx


def bits(tx):return encoded_payload(canonical(asdict(tx)))


@pytest.mark.parametrize('counter,alternate,taken',tuple(product(range(16),(0,1),(0,1))))
def test_all_qualification_combinations_train_only_weak_disagreement(counter,alternate,taken):
    for provider,owner,conditional,valid in product((0,1),repeat=4):
        meta=metadata(counter,alternate);meta['hasProvider']=provider
        votes,_=feedback_votes(bits(transaction(meta,taken=taken,owner=owner,conditional=conditional,valid=valid)))
        first=votes[0]
        qualified=bool(provider and owner and conditional and valid and counter in (3,4) and int(counter>=4)!=alternate)
        assert first['valid']==int(owner and conditional and valid)
        assert first['inc']==int(qualified and alternate==taken)
        assert first['dec']==int(qualified and int(counter>=4)==taken)


@pytest.mark.parametrize('index,value',tuple(product(range(16),(0,1,15,16,30,31))))
def test_all_sixteen_registers_net_votes_before_saturation_and_isolation(index,value):
    before=[16]*16;before[index]=value
    for directions in ((1,),(-1,),(-1,1),(1,1),(-1,-1)):
        votes=[dict(valid=1,index=index,inc=int(d==1),dec=int(d==-1),provider=True,weak=True,disagreement=True)
            for d in directions]
        after,_=update_selectors(before,votes)
        expected=before.copy();expected[index]=max(0,min(31,value+sum(directions)))
        assert after==tuple(expected)


def test_exercise_keeps_same_high_confidence_selector_through_both_boundaries():
    pair=TagePairModel(0,alternate_way=1,provider_way=0)
    pair.alternate=replace(pair.alternate,counter=3,useful=0)
    stages={};values=(16,)*16
    for label,outcomes in exercise_program():
        for taken in outcomes:
            votes,_=feedback_votes(bits(transaction(pair.metadata,taken=taken)))
            values,_=update_selectors(values,votes)
            pair.apply(taken)
            assert values[14:]==pair.selectors
        stages[label]=pair.selectors
    assert stages['lower-saturation'][1]==0
    assert stages['upper-sign-crossing'][1]==16
    assert stages['upper-saturation'][1]==31
    assert pair.provider.counter==4 and pair.metadata['altConf']==1


@pytest.mark.parametrize('provider,has_alt,mispredict',tuple(product((0,1),repeat=3)))
def test_read_mode_includes_alternate_use_and_any_mispredict(provider,has_alt,mispredict):
    meta=metadata();meta.update(useProvider=provider,hasAlt=has_alt)
    _,need_read=feedback_votes(bits(transaction(meta,mispredict=mispredict)))
    assert need_read==int(mispredict or (not provider and has_alt))


def sample(checker,tx=None,*,fire=(0,0,0,0),votes=None):
    empty=transaction(valid=0)
    return dict(reset=0,selectors=list(checker.values),enable=1,fire=fire,use_meta=1,
        raw_tags=[32]*8,reads=[[dict(valid=0,tag=0,counter=0,useful=0)]*2 for _ in range(8)],
        votes=votes or [dict(valid=0,index=0,inc=0,dec=0) for _ in range(8)],
        training=dict(valid=int(tx is not None),ready=1,bits=bits(tx or empty)))


def pending_update():
    coverage=SelectorCoverage();checker=TageSelectorChecker(coverage)
    initial=sample(checker);initial['reset']=1;checker.observe(initial,10)
    checker.observe(sample(checker),12)
    tx=transaction();source=SimpleNamespace(prediction_tick=6,meta_tick=8,meta=SimpleNamespace(resolve=tx.resolve_meta))
    checker.phase='exercise';checker.plan(tx,source)
    checker.observe(sample(checker,tx,fire=(1,1,0,0)),14)
    checker.observe(sample(checker,fire=(0,0,1,0)),16)
    t3=sample(checker,fire=(0,0,0,1))
    t3['votes'][0]=dict(valid=1,index=15,inc=1,dec=0)
    return checker,coverage,t3


def test_source_T2_T3_and_actual_register_effect_are_separately_associated():
    checker,coverage,t3=pending_update();checker.observe(t3,18)
    assert coverage.groups['update','reached'].samples==1
    assert coverage.groups['update','checked'].samples==0
    checker.observe(sample(checker),20)
    assert checker.summary()['selectors']==(16,)*15+(17,)
    assert coverage.groups['update','checked'].samples==1


@pytest.mark.parametrize('fault',('missing-T3','invalid-entry','wrong-index','no-increment','wrong-direction',
    'missing-effect','neighbor-corruption','late-effect'))
def test_dropped_qualifier_or_effect_preserves_reached_event_and_ordinary_failure(fault):
    checker,coverage,t3=pending_update()
    if fault=='missing-T3':t3['fire']=(0,0,0,0)
    elif fault=='invalid-entry':t3['votes'][0]['valid']=0
    elif fault=='wrong-index':t3['votes'][0]['index']=6
    elif fault=='no-increment':t3['votes'][0]['inc']=0
    elif fault=='wrong-direction':t3['votes'][0].update(inc=0,dec=1)
    if fault in ('missing-effect','neighbor-corruption','late-effect'):
        checker.observe(t3,18);following=sample(checker)
        if fault=='missing-effect':following['selectors'][15]-=1
        elif fault=='neighbor-corruption':following['selectors'][2]+=1
        observed=SimpleNamespace(value=following,event=SimpleNamespace(tick=22 if fault=='late-effect' else 20))
    else:
        observed=SimpleNamespace(value=t3,event=SimpleNamespace(tick=18))
    checker.capture(observed)
    with pytest.raises(ScoreboardMismatch):checker.raise_failure()
    assert coverage.groups['update','reached'].samples==1
    assert coverage.groups['update','checked'].samples==0
    assert checker.events[-1]['status']=='failed'


@pytest.mark.parametrize('fault',('payload','metadata','missing-plan'))
def test_source_mismatch_is_rejected_before_vote_credit(fault):
    coverage=SelectorCoverage();checker=TageSelectorChecker(coverage)
    reset=sample(checker);reset['reset']=1;checker.observe(reset,10)
    tx=transaction();source=SimpleNamespace(prediction_tick=6,meta_tick=8,meta=SimpleNamespace(resolve=deepcopy(tx.resolve_meta)))
    checker.phase='exercise'
    if fault=='metadata':
        tx.resolve_meta['tage_entries'][0]['altConf']^=1
        with pytest.raises(ScoreboardMismatch):checker.plan(tx,source)
    else:
        if fault!='missing-plan':checker.plan(tx,source)
        row=sample(checker,tx,fire=(1,1,0,0))
        if fault=='payload':row['training']['bits']['branches'][0]['bits']['target_addr']^=1
        with pytest.raises(ScoreboardMismatch):checker.observe(row,12)
    assert coverage.groups['update','reached'].samples==0


def public_witness():
    coverage=SelectorCoverage();checker=TageSelectorChecker(coverage)
    meta=metadata(alt=1);meta['hasAlt']=1
    tx=transaction(meta)
    source=SimpleNamespace(prediction_tick=20,meta_tick=24,prediction=SimpleNamespace(start_pc=tx.pc),
        meta=SimpleNamespace(resolve=tx.resolve_meta))
    fields=('hasProvider','providerTableIdx','providerWayIdx','providerTakenCtr_value',
        'hasAlt','altConf','altOrBasePred','useProvider')
    raw=dict(valid=1,taken=1,meta={key:meta[key] for key in fields})
    checker.records.append(dict(tick=22,expected_selectors=checker.values,
        prediction=dict(fire=1,pc=tx.pc,slots=[raw])))
    phr=SimpleNamespace(records=[dict(tick=24,parent=dict(s3_pc=tx.pc,s3_target=0x40020080,s3_taken=1),
        boundary=dict(s3=dict(prediction=dict(position=4))))])
    return checker,coverage,source,phr


def test_selector_consumer_checks_actual_TAGE_output_and_associated_BPU_final_prediction():
    checker,coverage,source,phr=public_witness()
    checker.check_public(source,4,phr=phr,positions=(4,),targets=(0x40020080,))
    assert coverage.groups['selection','reached'].samples==coverage.groups['selection','checked'].samples==1


@pytest.mark.parametrize('fault',('missing-S2','duplicate-S2','S2-pc','S2-valid','raw-valid','raw-taken',
    'raw-useProvider','raw-provider-counter','raw-confidence','metadata-useProvider',
    'missing-S3','duplicate-S3','S3-pc','S3-target','S3-taken','S3-position'))
def test_metadata_consistency_cannot_hide_prediction_output_or_source_failure(fault):
    checker,coverage,source,phr=public_witness()
    raw=checker.records[0]['prediction']['slots'][0]
    if fault=='missing-S2':checker.records.clear()
    elif fault=='duplicate-S2':checker.records.append(deepcopy(checker.records[0]))
    elif fault=='S2-pc':checker.records[0]['prediction']['pc']^=1
    elif fault=='S2-valid':checker.records[0]['prediction']['fire']=0
    elif fault=='raw-valid':raw['valid']=0
    elif fault=='raw-taken':raw['taken']=0
    elif fault=='raw-useProvider':raw['meta']['useProvider']^=1
    elif fault=='raw-provider-counter':raw['meta']['providerTakenCtr_value']^=1
    elif fault=='raw-confidence':raw['meta']['altConf']^=1
    elif fault=='metadata-useProvider':source.meta.resolve['tage_entries'][0]['useProvider']^=1
    elif fault=='missing-S3':phr.records.clear()
    elif fault=='duplicate-S3':phr.records.append(deepcopy(phr.records[0]))
    elif fault=='S3-position':phr.records[0]['boundary']['s3']['prediction']['position']^=1
    else:phr.records[0]['parent']['s3_'+fault[3:]]^=1
    with pytest.raises(ScoreboardMismatch):
        checker.check_public(source,4,phr=phr,positions=(4,),targets=(0x40020080,))
    assert coverage.groups['selection','checked'].samples==0
