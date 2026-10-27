"""Reject context substitution, younger equal reads and partial proof credit."""
from dataclasses import replace
from types import SimpleNamespace
import pytest
from toffee import ScoreboardMismatch

from bpuverify.utage.model.semantic import Context,indices
from bpuverify.utage.model.ancestor_lifetime import Program,PROFILES,RELATIONS,PC,MATCH_PC,MATCH_HISTORY,RULES
from tests.utage.scoreboard.test_ancestor_lifetime_model import derive
from bpuverify.utage.checker.ancestor_lifetime import Checks
from bpuverify.utage.coverage.ancestor_lifetime import Coverage



def witnesses(p):
    model,read,effects,event=derive(p)
    expected=model.prediction.values()
    actual=SimpleNamespace(hit=expected['0.hit'],taken=expected.get('0.taken',0),
        meta=dict(abtbResult=[dict(tableId=expected.get('0.provider',0),takenCtr_value=expected.get('0.counter',0))],
            readIndex=read.indices,foldedPathHistForTrain_hist=[dict(foldedHist=v) for v in Context.from_recent(MATCH_HISTORY).folds]))
    original=dict(tick=20 if p.relation=='read-with-write' else 24,events=event,read=read)
    response=dict(tick=original['tick']+2,frame=model.frame,actual=actual)
    effect=dict(tick=20,effects=effects,native=dict(changes=p.changes()))
    return original,response,effect


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
def test_independent_complete_two_ancestor_lifetime_passes(profile,relation):
    p=Program(profile,relation)
    Checks(p).lifetime(*witnesses(p))


FAULTS=('match-used-for-read','read-used-for-match-pc','read-used-for-match-history','younger-equal-read',
    'wrong-temporal-relation','wrong-response-hit','native-extra-change','missing-native-change')


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
@pytest.mark.parametrize('fault',FAULTS)
def test_context_substitution_wrong_age_or_fabricated_effect_is_rejected(profile,relation,fault):
    p=Program(profile,relation)
    read,response,effect=witnesses(p)
    if fault=='match-used-for-read':read['events']=replace(read['events'],read_pc=MATCH_PC,read_context=Context.from_recent(MATCH_HISTORY))
    elif fault=='read-used-for-match-pc':response['frame']=replace(response['frame'],pc=PC)
    elif fault=='read-used-for-match-history':response['frame']=replace(response['frame'],context=Context.from_recent(p.history))
    elif fault=='younger-equal-read':
        previous=read['read'];read['read']=replace(previous,entries=tuple(list(previous.entries)))
        assert read['read']==previous and read['read'].entries is not previous.entries
    elif fault=='wrong-temporal-relation':read['tick']=22 if relation=='read-with-write' else 20
    elif fault=='wrong-response-hit':response['actual'].hit^=1
    elif fault=='native-extra-change':effect['native']['changes']+=((3,0,1),)
    else:effect['native']['changes']=()
    with pytest.raises(ScoreboardMismatch) as error:Checks(p).lifetime(read,response,effect)
    assert error.value.context.request['program']==p.state()


DEFINED=(('provider-promotion','read-with-write'),('provider-promotion','read-after-write'),
         ('different-identity-replacement','read-with-write'))


@pytest.mark.parametrize('profile,relation',DEFINED)
@pytest.mark.parametrize('fault',('index','history','provider','counter','direction'))
def test_defined_public_metadata_cannot_erase_either_ancestor_or_mix_the_version(profile,relation,fault):
    p=Program(profile,relation)
    read,response,effect=witnesses(p)
    actual=response['actual']
    if fault=='index':actual.meta['readIndex']=indices(MATCH_PC,Context.from_recent(MATCH_HISTORY))
    elif fault=='history':actual.meta['foldedPathHistForTrain_hist']=[dict(foldedHist=v) for v in Context.from_recent(p.history).folds]
    elif fault=='provider':actual.meta['abtbResult'][0]['tableId']^=1
    elif fault=='counter':actual.meta['abtbResult'][0]['takenCtr_value']^=1
    else:actual.taken^=1
    with pytest.raises(ScoreboardMismatch):Checks(p).lifetime(read,response,effect)


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
@pytest.mark.parametrize('missing',RULES)
def test_any_missing_two_ancestor_obligation_prevents_checked_credit(profile,relation,missing):
    coverage=Coverage(Program(profile,relation))
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
def test_complete_lifetime_credits_only_its_own_semantic_program_once(profile,relation):
    coverage=Coverage(Program(profile,relation))
    for rule in RULES:coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage==25
    with pytest.raises(AssertionError):coverage.finish()
