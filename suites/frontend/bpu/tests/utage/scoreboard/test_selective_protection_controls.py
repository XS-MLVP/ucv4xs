"""Pure rejection controls for qualification, version ownership and coverage gates."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace,FunctionType
import pytest
from toffee import ScoreboardMismatch,TransferState
from suites.frontend.bpu.utage.model.semantic import Context, TRAIN_HISTORY_INDICES,Events,UtageReference
from suites.frontend.bpu.utage.transaction.types import UtagePrediction,UtageTraining
from tests.utage.scoreboard.test_semantic_model import lookup,feedback,learn,POSITIONS
from tests.utage.scoreboard.test_read_lifetime_model import bases
from suites.frontend.bpu.utage.model.selective_protection import Program,MODES,RULES,PC,POSITION,READ_PCS
from suites.frontend.bpu.utage.checker.selective_protection import Checks
from suites.frontend.bpu.utage.coverage.selective_protection import Coverage


def actual(prediction):
    row=prediction.values()
    return UtagePrediction(row['0.hit'],row.get('0.taken',0),dict(readIndex=prediction.frame.read.indices,
        foldedPathHistForTrain_hist=[dict(foldedHist=value) for value in prediction.frame.context.folds],
        abtbResult=[dict(tableId=row.get('0.provider',0),takenCtr_value=row.get('0.counter',0))]))


def cohort_witnesses(p):
    model=UtageReference()
    for step in p.steps[:p.boundary.ordinal]:
        source=lookup(model,PC,step.history,read_pc=READ_PCS[step.owner],read_history=0,bases=bases(step.base))
        learn(model,feedback(source,taken=bool(step.actual)))
    step=p.boundary
    teacher=lookup(model,PC,step.history,read_pc=READ_PCS[step.owner],read_history=0,bases=bases(step.base))
    request=feedback(teacher,taken=bool(step.actual))
    reads=[];responses=[];events=[];effect=None
    for ordinal,owner in enumerate(p.cohort_owners):
        event=Events(read_pc=READ_PCS[owner],read_context=Context(),select=True,pc=PC,
            context=Context.from_recent(64),positions=POSITIONS,bases=bases(owner),advance=True)
        if ordinal==1:event=replace(event,feedback=request)
        model.advance(event)
        if ordinal:responses.append(model.prediction)
        reads.append(model.read);events.append(event)
        if model.effects:
            assert effect is None
            effect=ordinal
    model.advance(event);responses.append(model.prediction)
    assert effect is not None
    rows={};transfers=[];actuals=[]
    for ordinal,(read,response,event) in enumerate(zip(reads,responses,events,strict=True)):
        tick=100+2*ordinal;value=actual(response)
        rows.setdefault(tick,dict(tick=tick)).update(read=read,events=event)
        rows.setdefault(tick+2,dict(tick=tick+2)).update(frame=response.frame,actual=value)
        transfers.append(SimpleNamespace(accepted_event=SimpleNamespace(tick=tick-2),
            completed_event=SimpleNamespace(tick=tick+2),state=TransferState.COMPLETED))
        actuals.append(value)
    return transfers,actuals,SimpleNamespace(at=rows.__getitem__,rows=rows),dict(tick=100+2*effect)


def learning_witnesses(p):
    rows=[];long=0
    for step in p.steps:
        versions={'0':dict(sequence=step.ordinal,next=(step.ordinal+1)%8,depth=8,new_cell=deepcopy(step.counter_cell))}
        if step.companion_allocation:
            versions['1']=dict(sequence=long,next=(long+1)%8,depth=8,new_cell=deepcopy(step.companion_cell));long+=1
        rows.append(dict(tick=200+2*step.ordinal,versions=versions,changes=step.changes,aged=False))
    return SimpleNamespace(records=rows,all_protection=lambda:p.protection_after(28),failure=None)


@pytest.mark.parametrize('first',(0,1))
@pytest.mark.parametrize('mode',MODES)
def test_checker_methods_are_not_shadowed_by_inherited_bookkeeping_fields(first,mode):
    checks=Checks(Program(first,mode))
    for name,value in vars(Checks).items():
        if isinstance(value,FunctionType):assert name not in vars(checks)


@pytest.mark.parametrize('first',(0,1))
def test_model_derived_lower_boundary_cohort_is_accepted(first):
    p=Program(first,'serial')
    rows=Checks(p).check_cohort(*cohort_witnesses(p))
    before,next_=tuple(row for row in rows if row['owner']==first)[::2]
    assert before['actual'][-1]!=next_['actual'][-1]


@pytest.mark.parametrize('first',(0,1))
@pytest.mark.parametrize('fault',('missing-original','late-completion','equal-younger-read','rebound-read-index',
    'long-provider-borrowed','wrong-match-history','wrong-response-direction','wrong-metadata-history','fake-ages'))
def test_direction_crossing_requires_exact_original_age_index_and_provider(first,fault):
    p=Program(first,'serial');transfers,actuals,monitor,effect=cohort_witnesses(p)
    read=monitor.rows[100];response=monitor.rows[102]
    if fault=='missing-original':transfers.pop()
    elif fault=='late-completion':transfers[0].completed_event.tick+=2
    elif fault=='equal-younger-read':
        old=read['read'];read['read']=replace(old,entries=tuple(list(old.entries)))
        assert old==read['read'] and old.entries is not read['read'].entries
    elif fault=='rebound-read-index':read['read']=replace(read['read'],indices=(511,511))
    elif fault=='long-provider-borrowed':actuals[0].meta['abtbResult'][0]['tableId']=1
    elif fault=='wrong-match-history':response['frame']=replace(response['frame'],context=Context())
    elif fault=='wrong-response-direction':response['actual']=replace(response['actual'],taken=1-response['actual'].taken)
    elif fault=='wrong-metadata-history':actuals[0].meta['foldedPathHistForTrain_hist'][TRAIN_HISTORY_INDICES[0]]['foldedHist']^=1
    else:effect['tick']=1000
    with pytest.raises(ScoreboardMismatch) as error:Checks(p).check_cohort(transfers,actuals,monitor,effect)
    assert error.value.context.request['point']


@pytest.mark.parametrize('first',(0,1))
@pytest.mark.parametrize('mode',MODES)
def test_all_learning_including_agreement_writes_and_legitimate_companions_is_compared(first,mode):
    p=Program(first,mode);checks=Checks(p);checks.prefix(learning_witnesses(p),28)
    assert checks.compared==28


@pytest.mark.parametrize('fault',('missing-agreement-write','invented-maintenance','other-cell-write',
    'saturation-wrap','unexpected-long-write','companion-dropped','companion-wrong-identity',
    'stale-counter','wrong-chronology','fake-pointer-lap','bad-endpoint'))
def test_final_values_or_useful_deltas_alone_cannot_prove_learning(fault):
    p=Program(0,'serial');monitor=learning_witnesses(p)
    agreement=next(step.ordinal for step in p.steps if step.phase=='base-agreement-lower')
    companion=next(step.ordinal for step in p.steps if step.companion_allocation)
    if fault=='missing-agreement-write':monitor.records.pop(agreement)
    elif fault=='invented-maintenance':monitor.records[agreement]['aged']=True
    elif fault=='other-cell-write':monitor.records[agreement]['changes']=((1,0,1),)
    elif fault=='saturation-wrap':monitor.records[p.boundary.ordinal]['changes']=((p.boundary.owner*256,0,3),)
    elif fault=='unexpected-long-write':monitor.records[agreement]['versions']['1']=deepcopy(monitor.records[companion]['versions']['1'])
    elif fault=='companion-dropped':monitor.records[companion]['versions'].pop('1')
    elif fault=='companion-wrong-identity':monitor.records[companion]['versions']['1']['new_cell']['index']^=256
    elif fault=='stale-counter':monitor.records[agreement]['versions']['0']['new_cell']['counter']^=1
    elif fault=='wrong-chronology':monitor.records[agreement]['versions']['0']['sequence']-=1
    elif fault=='fake-pointer-lap':monitor.records[agreement]['versions']['0']['next']^=1
    else:monitor.all_protection=lambda:(0,)*1024
    with pytest.raises(ScoreboardMismatch):Checks(p).prefix(monitor,28)


@pytest.mark.parametrize('mode',MODES)
def test_actual_two_source_feedback_cadence_is_checked(mode):
    p=Program(0,mode);group=p.groups[0];checks=Checks(p)
    checks.cadence(group,[dict(tick=100),dict(tick=102 if mode=='adjacent' else 114)])
    with pytest.raises(ScoreboardMismatch):checks.cadence(group,[dict(tick=100),dict(tick=114 if mode=='adjacent' else 102)])


@pytest.mark.parametrize('first',(0,1))
@pytest.mark.parametrize('mode',MODES)
@pytest.mark.parametrize('missing',RULES)
def test_missing_any_phase_or_preservation_rule_blocks_checked_credit(first,mode,missing):
    coverage=Coverage(Program(first,mode))
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('first',(0,1))
@pytest.mark.parametrize('mode',MODES)
def test_only_complete_phase_changing_ownership_receives_its_own_bins_once(first,mode):
    coverage=Coverage(Program(first,mode))
    for rule in RULES:coverage.reach(rule)
    coverage.finish();assert coverage.groups['checked'].coverage==25
    with pytest.raises(AssertionError):coverage.finish()
    with pytest.raises(ValueError):coverage.reach(RULES[0])
