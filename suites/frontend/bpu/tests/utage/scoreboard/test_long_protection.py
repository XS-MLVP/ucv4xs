"""Independent state derivation and rejection controls; no native DUT credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest
from toffee import ScoreboardMismatch,TransferState
from bpuverify.utage.model.semantic import Context,Events,UtageReference
from bpuverify.utage.model.long_protection import Program,MODES,LIFETIMES,RULES,PC,READ_PCS,SHADOW_CAPACITY
from bpuverify.utage.checker.long_protection import Checks
from bpuverify.utage.coverage.long_protection import Coverage
from tests.utage.scoreboard.test_semantic_model import lookup,feedback,learn,POSITIONS
from tests.utage.scoreboard.test_read_lifetime_model import bases,values
from tests.utage.scoreboard.test_selective_protection_controls import actual

PROGRAMS=tuple(Program(first,mode,life) for first in (0,1) for mode in MODES for life in LIFETIMES)


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_every_declared_long_lifetime_matches_the_independent_predictor_without_DUT(p):
    model=UtageReference();count=0;originals=[]
    for group in p.groups:
        requests=[]
        for step in group:
            source=lookup(model,PC,step.history,read_pc=READ_PCS[step.owner],read_history=0,bases=bases(step.base))
            assert values(source)==step.expected
            originals.append((source,deepcopy(source)));request=feedback(source,taken=bool(step.actual))
            if p.mode=='serial':learn(model,request)
            else:requests.append(request)
        if p.mode=='adjacent':
            for request in requests:model.advance(Events(feedback=request))
            model.advance();model.advance()
        count+=len(group)
        assert tuple(table.get(index,0) for table in model.useful for index in range(512))==p.protection_after(count)
    departed=p.lifetime=='after-unrelated-version-turnover'
    assert count==(39 if departed else 30) and model.low_tick==model.high_tick==8 and not model.aged
    assert tuple(cache.sequence for cache in model.updates)==((6,36) if departed else (4,28))
    assert all((model.updates[1].newest(p.read_indices(owner)[1]) is None)==departed for owner in (0,1))
    for owner in (0,1):
        for history,provider,counter,taken in p.final_consumers(owner):
            assert values(lookup(model,PC,history,read_pc=READ_PCS[owner],read_history=0,bases=bases(owner)))==(1,provider,counter,taken)
    assert all(source==saved for source,saved in originals)


def learning_witnesses(p):
    rows=[];sequences=[0,0]
    for step in p.steps:
        versions={}
        for table in step.tables:
            sequence=sequences[table];sequences[table]+=1
            versions[str(table)]=dict(sequence=sequence,next=(sequence+1)%8,depth=8,new_cell=step.cell(table))
        rows.append(dict(tick=200+2*step.ordinal,versions=versions,changes=step.changes,aged=False))
    return NS(records=rows,all_protection=lambda:p.protection_after(len(p.steps)),failure=None)


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_complete_promotions_and_long_feedback_preserve_all_short_experience(p):
    checks=Checks(p);checks.prefix(learning_witnesses(p),len(p.steps))
    assert checks.compared==len(p.steps)
    assert p.boundary.before.useful==p.boundary.new[1].useful==0
    assert p.boundary.before.taken!=p.boundary.new[1].taken
    assert all(step.tables==(1,) for step in p.steps[4:] if step.owner!=2)


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('fault',('promotion-short-lost','promotion-long-lost','short-rewritten-later',
    'invented-higher-allocation','other-identity','wrong-counter','wrapped-protection',
    'missing-agreement-write','wrong-chronology','wrong-endpoint'))
def test_wrong_identity_provider_or_final_only_checks_cannot_earn_a_pass(p,fault):
    monitor=learning_witnesses(p);promotion=2;late=p.boundary.ordinal
    if fault=='promotion-short-lost':monitor.records[promotion]['versions'].pop('0')
    elif fault=='promotion-long-lost':monitor.records[promotion]['versions'].pop('1')
    elif fault=='short-rewritten-later':monitor.records[late]['versions']['0']=deepcopy(monitor.records[2]['versions']['0'])
    elif fault=='invented-higher-allocation':monitor.records[late]['versions']['2']=deepcopy(monitor.records[late]['versions']['1'])
    elif fault=='other-identity':monitor.records[late]['versions']['1']['new_cell']['index']^=256
    elif fault=='wrong-counter':monitor.records[late]['versions']['1']['new_cell']['counter']^=1
    elif fault=='wrapped-protection':monitor.records[late]['changes']=((512+p.first*256,0,3),)
    elif fault=='missing-agreement-write':monitor.records.pop(next(s.ordinal for s in p.steps if s.phase=='base-agreement-lower'))
    elif fault=='wrong-chronology':monitor.records[late]['versions']['1']['sequence']-=1
    else:monitor.all_protection=lambda:(0,)*1024
    with pytest.raises(ScoreboardMismatch) as error:Checks(p).prefix(monitor,len(p.steps))
    assert error.value.context.request['point']


def cohort_witnesses(p):
    model=UtageReference()
    for step in p.steps[:p.boundary.ordinal]:
        source=lookup(model,PC,0,read_pc=READ_PCS[step.owner],read_history=0,bases=bases(step.base))
        learn(model,feedback(source,taken=bool(step.actual)))
    step=p.boundary
    source=lookup(model,PC,0,read_pc=READ_PCS[step.owner],read_history=0,bases=bases(step.base))
    request=feedback(source,taken=bool(step.actual));reads=[];responses=[];events=[];effect=None
    for ordinal,owner in enumerate(p.cohort_owners):
        event=Events(read_pc=READ_PCS[owner],read_context=Context(),select=True,pc=PC,
            context=Context(),positions=POSITIONS,bases=bases(owner),advance=True)
        if ordinal==1:event=replace(event,feedback=request)
        model.advance(event)
        if ordinal:responses.append(model.prediction)
        reads.append(model.read);events.append(event)
        if model.effects:assert effect is None;effect=ordinal
    model.advance(event);responses.append(model.prediction)
    assert effect is not None
    rows={};transfers=[];actuals=[]
    for ordinal,(read,response,event) in enumerate(zip(reads,responses,events,strict=True)):
        tick=100+2*ordinal;value=actual(response)
        rows.setdefault(tick,dict(tick=tick)).update(read=read,events=event)
        rows.setdefault(tick+2,dict(tick=tick+2)).update(frame=response.frame,actual=value)
        transfers.append(NS(accepted_event=NS(tick=tick-2),completed_event=NS(tick=tick+2),state=TransferState.COMPLETED))
        actuals.append(value)
    return transfers,actuals,NS(at=rows.__getitem__,rows=rows),dict(tick=100+2*effect)


@pytest.mark.parametrize('first',(0,1))
def test_independent_long_boundary_responses_keep_all_three_original_read_ages(first):
    p=Program(first,'serial');rows=Checks(p).check_cohort(*cohort_witnesses(p))
    assert {row['relation'] for row in rows if row['owner']==first}=={'before','same-boundary','after'}


@pytest.mark.parametrize('first',(0,1))
@pytest.mark.parametrize('fault',('missing-original','late-completion','equal-younger-read',
    'wrong-index','short-provider-borrowed','wrong-history','wrong-direction','fake-read-ages'))
def test_old_long_response_cannot_borrow_a_younger_version_or_short_provider(first,fault):
    p=Program(first,'serial');transfers,actuals,monitor,effect=cohort_witnesses(p)
    read=monitor.rows[100];response=monitor.rows[102]
    if fault=='missing-original':transfers.pop()
    elif fault=='late-completion':transfers[0].completed_event.tick+=2
    elif fault=='equal-younger-read':read['read']=replace(read['read'],entries=tuple(list(read['read'].entries)))
    elif fault=='wrong-index':read['read']=replace(read['read'],indices=(511,511))
    elif fault=='short-provider-borrowed':actuals[0].meta['abtbResult'][0]['tableId']=0
    elif fault=='wrong-history':response['frame']=replace(response['frame'],context=Context.from_recent(64))
    elif fault=='wrong-direction':response['actual']=replace(response['actual'],taken=1-response['actual'].taken)
    else:effect['tick']=1000
    with pytest.raises(ScoreboardMismatch):Checks(p).check_cohort(transfers,actuals,monitor,effect)


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('missing',RULES)
def test_every_semantic_obligation_is_required_for_checked_credit(p,missing):
    c=Coverage(p)
    for rule in RULES:
        if rule!=missing:c.reach(rule)
    with pytest.raises(AssertionError):c.finish()
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_one_complete_lifetime_credits_only_its_declared_profile(p):
    c=Coverage(p)
    for rule in RULES:c.reach(rule)
    c.finish();assert c.groups['checked'].coverage==12.5
    with pytest.raises(AssertionError):c.finish()


@pytest.mark.parametrize('first,mode',((2,'serial'),(True,'serial'),(0,'bank1'),(1,'slot0')))
def test_physical_coordinates_are_not_extra_behavioral_profiles(first,mode):
    with pytest.raises(ValueError):Program(first,mode)


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_real_cache_departure_is_required_not_just_a_late_query_label(p):
    departed=p.lifetime=='after-unrelated-version-turnover'
    cells=[dict(valid=1,index=1 if departed else 256*(i%2)) for i in range(SHADOW_CAPACITY)]
    monitor=NS(long_snapshot=dict(tick=900,cells=cells));checks=Checks(p);checks.compared=len(p.steps)
    witness=checks.consumer_lifetime(monitor);assert witness['all_targets_absent']==departed
    monitor.long_snapshot['cells'][0]['index']=0 if departed else 1
    if not departed:
        for cell in monitor.long_snapshot['cells']:cell['index']=1
    with pytest.raises(ScoreboardMismatch):checks.consumer_lifetime(monitor)
