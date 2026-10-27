"""Independent-model witnesses and rejection controls; no DUT coverage credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import pytest

from toffee import ScoreboardMismatch,TransferState
from bpuverify.utage.model.semantic import Context,Events,UtageReference
from bpuverify.utage.transaction.types import UtagePrediction,UtageTraining
from tests.utage.scoreboard.test_semantic_model import lookup,feedback,learn,POSITIONS
from tests.utage.scoreboard.test_read_lifetime_model import bases,values
from bpuverify.utage.model.query_identity import Program,MODES,RULES,PC,POSITION,READ_PCS
from bpuverify.utage.checker.query_identity import Checks
from bpuverify.utage.coverage.query_identity import Coverage



def prepared(p):
    model=UtageReference()
    for owner in (0,1):
        cold=lookup(model,PC,read_pc=READ_PCS[owner],bases=bases(owner))
        learn(model,feedback(cold,taken=not owner))
    return model


def derive(p):
    model=prepared(p)
    source=lookup(model,PC,read_pc=READ_PCS[p.teacher],bases=bases(p.teacher))
    request=feedback(source,taken=not p.teacher)
    reads=[];responses=[];events=[];effect=None
    for ordinal,owner in enumerate(p.cohort_owners):
        event=Events(read_pc=READ_PCS[owner],read_context=Context(),select=True,pc=PC,
            context=Context(),positions=POSITIONS,bases=bases(owner),advance=True)
        if ordinal==1:event=replace(event,feedback=request)
        model.advance(event)
        if ordinal:responses.append(model.prediction)
        reads.append(model.read);events.append(event)
        if model.effects:
            assert effect is None
            effect=ordinal
    model.advance(event);responses.append(model.prediction)
    assert effect is not None
    return model,reads,responses,events,effect


def actual(prediction):
    row=prediction.values()
    return UtagePrediction(row['0.hit'],row.get('0.taken',0),dict(readIndex=prediction.frame.read.indices,
        abtbResult=[dict(tableId=row.get('0.provider',0),takenCtr_value=row.get('0.counter',0))]))


def witnesses(p):
    _,reads,responses,events,effect=derive(p)
    rows={};transfers=[];actuals=[]
    for ordinal,(read,response,event) in enumerate(zip(reads,responses,events,strict=True)):
        tick=100+2*ordinal;prediction=actual(response)
        rows.setdefault(tick,dict(tick=tick)).update(events=event,read=read)
        rows.setdefault(tick+2,dict(tick=tick+2)).update(frame=response.frame,actual=prediction)
        transfers.append(SimpleNamespace(accepted_event=SimpleNamespace(tick=tick-2),
            completed_event=SimpleNamespace(tick=tick+2),state=TransferState.COMPLETED))
        actuals.append(prediction)
    return transfers,actuals,SimpleNamespace(at=rows.__getitem__,rows=rows),dict(tick=100+2*effect)


@pytest.mark.parametrize('teacher',(0,1))
@pytest.mark.parametrize('mode',MODES)
def test_complete_independent_model_witnesses_have_two_owners_and_three_target_ages(teacher,mode):
    p=Program(teacher,mode)
    rows=Checks(p).responses(*witnesses(p))
    assert len(rows)==7 and {r['owner'] for r in rows}=={0,1}


@pytest.mark.parametrize('teacher',(0,1))
@pytest.mark.parametrize('mode',MODES)
def test_both_feedback_cadences_derive_mixed_owner_retention_turnover_without_state_seeding(teacher,mode):
    p=Program(teacher,mode);model,*_=derive(p)
    initial=model.updates[0].recent[-1].sequence
    sources=[]
    for owner in p.turnover_owners:
        source=lookup(model,PC,read_pc=READ_PCS[owner],bases=bases(owner))
        if mode=='serial':learn(model,feedback(source,taken=not owner))
        else:sources.append(feedback(source,taken=not owner))
    if mode=='adjacent':
        for source in sources:model.advance(Events(feedback=source))
        model.advance();model.advance()
    assert not any(v.sequence==initial for v in model.updates[0].recent)
    for owner in (0,1):
        assert values(lookup(model,PC,read_pc=READ_PCS[owner],bases=bases(owner)))==p.expected(owner,subsequent=8)
    assert tuple(table.get(index,0) for table in model.useful for index in range(512))==p.protection('turnover')


FAULTS=('missing-query','missing-response','nonadjacent-admission','late-response','pending-transfer',
    'idle-read','read-high-bit-lost','read-history-rebound','matching-context-changed',
    'equal-younger-read','response-uses-other-original','actual-index-high-bit-lost',
    'other-response-version-used','monitored-version-wrong','fabricated-read-ages')


@pytest.mark.parametrize('teacher',(0,1))
@pytest.mark.parametrize('fault',FAULTS)
def test_current_pc_tag_or_low_index_cannot_impersonate_an_original_full_identity(teacher,fault):
    p=Program(teacher,'serial');transfers,actuals,monitor,effect=witnesses(p)
    high=next(i for i,owner in enumerate(p.cohort_owners) if owner==1)
    read=monitor.rows[100+2*high];response=monitor.rows[102+2*high]
    if fault=='missing-query':transfers.pop()
    elif fault=='missing-response':actuals.pop()
    elif fault=='nonadjacent-admission':transfers[1].accepted_event.tick+=2
    elif fault=='late-response':transfers[0].completed_event.tick+=2
    elif fault=='pending-transfer':transfers[0].state=TransferState.PROCESSING
    elif fault=='idle-read':read['events']=replace(read['events'],select=False)
    elif fault=='read-high-bit-lost':read['read']=replace(read['read'],indices=(0,0))
    elif fault=='read-history-rebound':read['events']=replace(read['events'],read_context=Context.from_recent(1))
    elif fault=='matching-context-changed':response['frame']=replace(response['frame'],pc=PC+2)
    elif fault=='equal-younger-read':
        old=read['read'];read['read']=replace(old,entries=tuple(list(old.entries)))
        assert read['read']==old and read['read'].entries is not old.entries
    elif fault=='response-uses-other-original':response['frame']=replace(response['frame'],read=monitor.rows[100+2*(1-high)]['read'])
    elif fault=='actual-index-high-bit-lost':actuals[high].meta['readIndex']=(0,0)
    elif fault=='other-response-version-used':actuals[high]=actuals[1-high]
    elif fault=='monitored-version-wrong':response['actual']=replace(response['actual'],taken=1-response['actual'].taken)
    else:effect['tick']=1000
    with pytest.raises(ScoreboardMismatch) as error:Checks(p).responses(transfers,actuals,monitor,effect)
    assert error.value.context.request['point'] and error.value.context.request['program']==p.state()


def version_witnesses(p):
    public_ticks=(100,114,130,*tuple(150+(2 if p.mode=='adjacent' else 14)*i for i in range(8)))
    rows=[dict(tick=tick+6,next=(i+1)%8,logical_sequence=i,depth=8,new_cell=deepcopy(v['cell']))
        for i,(tick,v) in enumerate(zip(public_ticks,p.versions(),strict=True))]
    return SimpleNamespace(versions=rows,public=[dict(tick=tick) for tick in public_ticks],
        effects=[dict(native=dict(changes=v['protection_changes'])) for v in p.versions()])


@pytest.mark.parametrize('teacher',(0,1))
@pytest.mark.parametrize('mode',MODES)
def test_native_chronology_requires_full_identity_and_selected_feedback_cadence(teacher,mode):
    p=Program(teacher,mode);Checks(p).turnover(version_witnesses(p))


@pytest.mark.parametrize('fault',('missing-write','duplicate-boundary','shortened-depth','skipped-version',
    'fake-pointer-motion','high-index-lost','other-counter','invalid-cell','wrong-feedback-cadence',
    'transient-other-cell-write','missing-saturation-effect'))
@pytest.mark.parametrize('mode',MODES)
def test_pointer_lap_or_latest_value_does_not_prove_owned_version_turnover(mode,fault):
    p=Program(0,mode);monitor=version_witnesses(p)
    if fault=='missing-write':monitor.versions.pop()
    elif fault=='duplicate-boundary':monitor.versions[1]['tick']=monitor.versions[0]['tick']
    elif fault=='shortened-depth':monitor.versions[1]['depth']=4
    elif fault=='skipped-version':monitor.versions[1]['logical_sequence']=0
    elif fault=='fake-pointer-motion':monitor.versions[1]['next']=1
    elif fault=='high-index-lost':monitor.versions[1]['new_cell']['index']=0
    elif fault=='other-counter':monitor.versions[1]['new_cell']['counter']=4
    elif fault=='invalid-cell':monitor.versions[1]['new_cell']['data_valid']=0
    elif fault=='wrong-feedback-cadence':
        for i,row in enumerate(monitor.public[-8:]):row['tick']=150+(14 if mode=='adjacent' else 2)*i
    elif fault=='transient-other-cell-write':monitor.effects[3]['native']['changes']+=((1,0,1),)
    else:monitor.effects.pop()
    with pytest.raises(ScoreboardMismatch):Checks(p).turnover(monitor)


@pytest.mark.parametrize('claimed_owner',(0,1))
def test_feedback_cannot_borrow_another_original_with_the_same_matching_pc_and_tag(claimed_owner):
    p=Program(0,'serial');checks=Checks(p);owner=1-claimed_owner
    source=UtagePrediction(1,1-owner,dict(readIndex=p.read_indices(owner),abtbResult=[dict(tableId=0,takenCtr_value=p.initial(owner))]))
    ordinal=checks.remember(source)
    transaction=UtageTraining(PC,POSITION,p.actual(claimed_owner),deepcopy(source.meta))
    with pytest.raises(ScoreboardMismatch):checks.owned_feedback(claimed_owner,ordinal,transaction)


@pytest.mark.parametrize('teacher',(0,1))
@pytest.mark.parametrize('mode',MODES)
@pytest.mark.parametrize('missing',RULES)
def test_missing_any_mixed_owner_obligation_prevents_checked_credit(teacher,mode,missing):
    coverage=Coverage(Program(teacher,mode))
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('teacher',(0,1))
@pytest.mark.parametrize('mode',MODES)
def test_complete_alias_case_credits_only_its_own_semantic_combination_once(teacher,mode):
    coverage=Coverage(Program(teacher,mode))
    for rule in RULES:coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage==25
    with pytest.raises(AssertionError):coverage.finish()
    with pytest.raises(ValueError):coverage.reach(RULES[0])


@pytest.mark.parametrize('teacher,mode',((True,'serial'),(2,'serial'),(None,'serial'),(0,'bank-sweep')))
def test_unknown_ownership_or_communication_modes_are_rejected(teacher,mode):
    with pytest.raises(ValueError):Program(teacher,mode)
