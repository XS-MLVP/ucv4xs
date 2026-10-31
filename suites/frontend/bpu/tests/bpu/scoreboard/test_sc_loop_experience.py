"""Algorithm and evidence rejection controls; no synthetic DUT coverage."""
from copy import deepcopy
from dataclasses import replace
import pytest

from suites.frontend.bpu.bpu.model.sc_loop_experience import Program,PROFILES,RULES
from suites.frontend.bpu.bpu.coverage.sc_loop_experience import Coverage
from suites.frontend.bpu.sc.model.semantic import Context,Events,ScReference
from suites.frontend.bpu.sc.transaction.types import ScHistory,ScBaseBranch,ScBatchTraining,ScBranchFeedback

pytestmark=pytest.mark.toffee_functional_coverage(False)


def lookup(model,program,history):
    model.advance(Events(pc=program.b,context=Context.from_history(history)))
    model.advance(Events(advance=True))
    model.advance(Events(select=True,branches=(ScBaseBranch(program.position,program.provider_counter),
        *(ScBaseBranch(i,0,0,0,0) for i in range(1,10)))))
    return model.prediction


def drain(model):
    for _ in range(16):
        dirty=any(row is not None and row.dirty for banks in model.writes for cache in banks for row in cache.rows)
        if model.learning is None and not model.pending and not dirty:return
        model.advance()
    raise AssertionError('model learning and pending writes failed to retire')


def feedback(program,prediction,history,taken):
    return ScBatchTraining(program.b,prediction.metadata(),
        (ScBranchFeedback(program.position,int(taken),0),),history)


@pytest.mark.parametrize('profile',PROFILES)
def test_existing_reference_keeps_old_loop_feedback_and_young_private_experience_separate(profile):
    p=Program(profile);model=ScReference()
    old=ScHistory(0x93,255,15,p.old_iteration)
    young=replace(old,loop=p.young_iteration)
    originals=[lookup(model,p,old) for _ in range(p.teaching_count)]
    snapshots=deepcopy(originals)
    for original in originals:
        model.advance(Events(feedback=feedback(p,original,old,True),feedback_context=Context.from_history(old)))
        drain(model)
    strong=lookup(model,p,old)
    assert strong.used[0]==1 and strong.sums[0]>originals[0].sums[0]
    young_before=lookup(model,p,young)
    before=deepcopy(model.memory),model.thresholds.values
    model.advance(Events(feedback=feedback(p,strong,old,True),feedback_context=Context.from_history(old)))
    drain(model)
    assert before==(model.memory,model.thresholds.values)
    correct=lookup(model,p,old)
    model.advance(Events(feedback=feedback(p,correct,old,False),feedback_context=Context.from_history(old)))
    drain(model)
    changed=lookup(model,p,old);fresh_young=lookup(model,p,young)
    assert changed.used[0]==1 and changed.directions[0]==1
    assert all(a!=b for a,b in zip(correct.read.weights,changed.read.weights,strict=True))
    assert fresh_young.read.weights[6]==young_before.read.weights[6]
    assert fresh_young.read.weights[7]!=young_before.read.weights[7]
    assert originals==snapshots


@pytest.mark.parametrize('profile',PROFILES)
def test_instruction_stage_and_submission_mode_are_not_storage_coordinate_parameters(profile):
    p=Program(profile)
    assert p.young_iteration>p.old_iteration>0 and p.old_iteration!=p.young_iteration
    assert p.teaching_count==3
    assert 8*(2*(p.teaching_count-1)+1)>1130//32
    assert 8*(2*(p.teaching_count-2)+1)<=1130//32
    assert p.state()['physical_enumeration'] is False
    assert p.state()['new_predictor_algorithm'] is False


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('fault',('zero','current-instead-of-original','boolean','overflow'))
def test_a_current_or_invalid_iteration_cannot_impersonate_the_old_original(profile,fault):
    p=Program(profile)
    value={'zero':0,'current-instead-of-original':p.young_iteration,'boolean':True,'overflow':256}[fault]
    with pytest.raises(ValueError):p.require_iteration(value)


@pytest.mark.parametrize('missing',RULES)
def test_every_semantic_obligation_is_required_before_checked_credit(missing):
    c=Coverage(PROFILES[0])
    for rule in RULES:
        if rule!=missing:c.record(rule,10)
    with pytest.raises(AssertionError):c.finish()
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
def test_complete_profile_has_only_its_own_semantic_bins_without_duplicate_credit(profile):
    c=Coverage(profile)
    for rule in RULES:c.record(rule,10)
    c.finish()
    assert c.groups['checked'].coverage==25
    with pytest.raises(AssertionError):c.finish()


@pytest.mark.parametrize('profile',(None,'bank0','early-valid.queue','steady.ready-valid'))
def test_unknown_or_protocol_named_profiles_are_rejected(profile):
    with pytest.raises(ValueError):Program(profile)
