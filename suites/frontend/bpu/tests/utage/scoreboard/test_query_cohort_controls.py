"""Pure adversarial controls; none creates hardware or functional PASS credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import pytest

from toffee import ScoreboardMismatch,TransferState
from bpuverify.utage.model.semantic import Events,tag
from bpuverify.utage.transaction.types import UtagePrediction,UtageTraining
from bpuverify.utage.case.definitions import SHADOW_CAPACITY
from bpuverify.utage.model.query_cohort import Program,PROFILES,ANCESTRIES,COHORT_SIZE,RULES,PC,POSITION
from bpuverify.utage.checker.query_cohort import Checks
from bpuverify.utage.coverage.query_cohort import Coverage
from tests.utage.scoreboard.test_query_cohort_model import derive



def prediction(reference):
    row=reference.values()
    return UtagePrediction(row['0.hit'],row.get('0.taken',0),dict(abtbResult=[dict(
        tableId=row.get('0.provider',0),takenCtr_value=row.get('0.counter',0))]))


def witnesses(p):
    _,originals,responses,effect=derive(p)
    rows={};actuals=[];transfers=[]
    for ordinal,(source,response) in enumerate(responses):
        tick=100+2*ordinal
        rows.setdefault(tick,dict(tick=tick)).update(events=Events(select=True,read_pc=PC,
            read_context=p.read_context),read=originals[source])
        actual=prediction(response)
        rows.setdefault(tick+2,dict(tick=tick+2)).update(frame=response.frame,actual=actual)
        actuals.append(actual)
        transfers.append(SimpleNamespace(accepted_event=SimpleNamespace(tick=tick-2),
            completed_event=SimpleNamespace(tick=tick+2),state=TransferState.COMPLETED))
    return transfers,actuals,SimpleNamespace(at=rows.__getitem__,rows=rows),dict(tick=100+2*effect)


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('ancestry',ANCESTRIES)
def test_complete_model_derived_occurrences_are_accepted(profile,ancestry):
    p=Program(profile,ancestry)
    assert len(Checks(p).responses(*witnesses(p)))==COHORT_SIZE


FAULTS=('missing-query','missing-response','nonadjacent-admission','late-response','pending-transfer',
    'idle-read','wrong-read-index','wrong-read-history','wrong-match-history','equal-younger-read',
    'merged-occurrences','wrong-returned-version','wrong-monitored-version','fabricated-ages')


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('ancestry',ANCESTRIES)
@pytest.mark.parametrize('fault',FAULTS)
def test_wrong_owner_wrong_version_or_incomplete_cohort_is_rejected(profile,ancestry,fault):
    p=Program(profile,ancestry)
    transfers,actuals,monitor,effect=witnesses(p)
    read=monitor.rows[100];response=monitor.rows[102]
    if fault=='missing-query':transfers.pop()
    elif fault=='missing-response':actuals.pop()
    elif fault=='nonadjacent-admission':transfers[1].accepted_event.tick+=2
    elif fault=='late-response':transfers[0].completed_event.tick+=2
    elif fault=='pending-transfer':transfers[0].state=TransferState.PROCESSING
    elif fault=='idle-read':read['events']=replace(read['events'],select=False)
    elif fault=='wrong-read-index':read['read']=replace(read['read'],indices=(511,511))
    elif fault=='wrong-read-history':read['events']=replace(read['events'],read_context=replace(
        p.read_context,folds=(p.read_context.folds[0]^1,*p.read_context.folds[1:])))
    elif fault=='wrong-match-history':response['frame']=replace(response['frame'],context=replace(p.match_context,folds=(p.match_context.folds[0]^1,*p.match_context.folds[1:])))
    elif fault=='equal-younger-read':
        old=read['read'];read['read']=replace(old,entries=tuple(list(old.entries)))
        assert old==read['read'] and old.entries is not read['read'].entries
    elif fault=='merged-occurrences':
        second=monitor.rows[102]
        second['read']=replace(second['read'],entries=read['read'].entries)
        monitor.rows[104]['frame']=replace(monitor.rows[104]['frame'],read=second['read'])
    elif fault=='wrong-returned-version':actuals[0]=replace(actuals[0],hit=1-actuals[0].hit)
    elif fault=='wrong-monitored-version':response['actual']=replace(response['actual'],hit=1-response['actual'].hit)
    else:effect['tick']=1000
    with pytest.raises(ScoreboardMismatch) as error:Checks(p).responses(transfers,actuals,monitor,effect)
    assert error.value.context.request['point']
    assert error.value.context.request['program']==p.state()


def versions(p):
    return [dict(tick=100+2*i,next=(3+i)%SHADOW_CAPACITY,depth=SHADOW_CAPACITY,
        logical_sequence=12+i,new_cell=dict(valid=1,data_valid=1,index=p.target_index,
            tag=tag(p.teacher_pc,p.read_context,p.target_table),position=POSITION,counter=p.counter(i)))
        for i in range(SHADOW_CAPACITY+1)]


@pytest.mark.parametrize('profile',PROFILES)
def test_complete_logical_version_lap_is_accepted_without_physical_feature_points(profile):
    p=Program(profile,ANCESTRIES[0])
    Checks(p).turnover(SimpleNamespace(versions=versions(p)))


@pytest.mark.parametrize('fault',('missing-write','duplicate-boundary','shortened-capacity','skipped-epoch',
    'fake-pointer-lap','different-owner','different-counter','invalid-data'))
def test_count_or_pointer_motion_alone_cannot_prove_version_turnover(fault):
    p=Program(PROFILES[0],ANCESTRIES[0]);rows=versions(p)
    if fault=='missing-write':rows.pop()
    elif fault=='duplicate-boundary':rows[1]['tick']=rows[0]['tick']
    elif fault=='shortened-capacity':rows[1]['depth']=4
    elif fault=='skipped-epoch':rows[1]['logical_sequence']+=1
    elif fault=='fake-pointer-lap':rows[1]['next']=rows[0]['next']
    elif fault=='different-owner':rows[1]['new_cell']['index']^=1
    elif fault=='different-counter':rows[1]['new_cell']['counter']^=1
    else:rows[1]['new_cell']['data_valid']=0
    with pytest.raises(ScoreboardMismatch):Checks(p).turnover(SimpleNamespace(versions=rows))


def feedback_checks():
    p=Program(PROFILES[0],ANCESTRIES[0]);checks=Checks(p)
    sources=[UtagePrediction(1,1,dict(abtbResult=[dict(tableId=0,takenCtr_value=4+i)])) for i in range(2)]
    for source in sources:
        ordinal=checks.remember(source)
        checks.original_feedback(ordinal,UtageTraining(PC,POSITION,1,deepcopy(source.meta),mispredict=0))
    return checks,SimpleNamespace(public=[dict(tick=100+2*i,bits=deepcopy(bits))
        for i,bits in enumerate(checks.expected_feedback)])


def test_actual_feedback_envelopes_preserve_both_complete_payload_and_chronology():
    checks,monitor=feedback_checks();checks.finish(monitor)


@pytest.mark.parametrize('fault',('changed-payload','duplicate-tick','missing-feedback','mutated-original'))
def test_feedback_or_original_snapshot_corruption_is_rejected(fault):
    checks,monitor=feedback_checks()
    if fault=='changed-payload':monitor.public[0]['bits']['branch']['taken']^=1
    elif fault=='duplicate-tick':monitor.public[1]['tick']=monitor.public[0]['tick']
    elif fault=='missing-feedback':monitor.public.pop()
    else:checks.originals[0][0].meta['abtbResult'][0]['takenCtr_value']=7
    with pytest.raises(ScoreboardMismatch):checks.finish(monitor)


def test_renaming_one_response_cannot_create_a_fresh_learning_source():
    checks,_=feedback_checks()
    with pytest.raises(ScoreboardMismatch):checks.remember(checks.originals[0][0])


def test_original_teacher_cannot_be_replayed_to_fake_retention_turnover():
    checks,_=feedback_checks();source=checks.originals[0][0]
    with pytest.raises(ValueError):checks.original_feedback(0,UtageTraining(PC,POSITION,1,deepcopy(source.meta)))


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('ancestry',ANCESTRIES)
@pytest.mark.parametrize('missing',RULES)
def test_any_missing_cohort_or_preservation_obligation_blocks_all_checked_credit(profile,ancestry,missing):
    coverage=Coverage(Program(profile,ancestry))
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('ancestry',ANCESTRIES)
def test_only_complete_semantic_cohort_receives_its_own_checked_bins_once(profile,ancestry):
    coverage=Coverage(Program(profile,ancestry))
    for rule in RULES:coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage==pytest.approx(100/6)
    with pytest.raises(AssertionError):coverage.finish()
    with pytest.raises(ValueError):coverage.reach(RULES[0])
