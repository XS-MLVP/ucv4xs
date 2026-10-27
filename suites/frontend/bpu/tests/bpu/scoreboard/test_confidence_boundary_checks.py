"""Adversarial intermediate observations must fail even if final values match."""
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.model.tage.confidence_boundary import PROGRAMS
from tests.bpu.scoreboard.confidence_boundary_fixtures import mixed,relearned,released,completed,packet
from tests.bpu.scoreboard.test_partial_reuse import transfer


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_actual_steps_sources_services_and_all_twelve_consumers_required_for_checked(program):
    checks,_,retired=completed(program)
    assert checks.coverage.groups['checked'].coverage==0 and not retired
    checks.finish()
    assert all(group.coverage==100 for group in checks.coverage.groups.values())
    assert len(retired)==len(set(retired))


@pytest.mark.parametrize('fault',('old-proposal-as-current','wrapped-counter','wrong-neighbor','missing-front',
                                 'ready-under-read','main-not-ready','main-extra-update','main-missing-update'))
def test_corrupt_intermediate_or_auxiliary_capacity_is_rejected(fault):
    def corrupt(index,row):
        if index!=1:return
        front=row['state']['writes'][1]
        if fault=='old-proposal-as-current':front['bits']['counter']=6
        elif fault=='wrapped-counter':front['bits']['counter']=7
        elif fault=='wrong-neighbor':front['bits']['tag']^=1
        elif fault=='missing-front':front['valid']=0
        elif fault=='ready-under-read':front['ready']=1
        elif fault=='main-not-ready':row['main'][0]['direction']['ready']=0
        elif fault=='main-extra-update':row['main'][1]['direction']['valid']=1
        else:row['main'][0]['direction']['valid']=0
    with pytest.raises(AssertionError):
        checks,_,_=relearned(PROGRAMS[0],front_fault=corrupt);checks.pending()


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_last_accepted_source_without_its_proposal_cannot_be_hidden_by_matching_final_state(program):
    checks,_,_=relearned(program,missing_last=True)
    with pytest.raises(AssertionError,match='all complete actual proposals'):checks.pending()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('next_tick',(100,101))
def test_capacity_gaps_do_not_waive_distinct_rising_input_order(next_tick):
    checks,_,_=mixed(PROGRAMS[0])
    with pytest.raises(AssertionError):checks.late_input_cadence(100,next_tick)
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('program',PROGRAMS[2:],ids=lambda p:p.name)
def test_full_roundtrip_also_closes_with_non_shifting_prediction_history(program):
    checks,_,_=completed(program,traffic='fallthrough');checks.finish()
    assert all(group.coverage==100 for group in checks.coverage.groups.values())


@pytest.mark.parametrize('fold_index',(0,8))
def test_stale_training_history_cannot_borrow_correct_original_provider_metadata(fold_index):
    checks,_,_=mixed(PROGRAMS[0]);checks.arm_mixed()
    row=packet(checks,training=True);folds=list(row['train_folds']);folds[fold_index]^=1;row['train_folds']=folds
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=100400),row)
    with pytest.raises(AssertionError,match='original training history must remain reconstructible'):checks.raise_failure()
    assert checks.pipeline.model.sources.tage.state()==before and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('same-prediction-reused','missing-step','missing-main-update','wrong-final-confidence'))
def test_owner_step_and_auxiliary_acceptance_obligations_cannot_be_forged(fault):
    if fault=='same-prediction-reused':
        checks,_,_=mixed(PROGRAMS[0]);first,second=PROGRAMS[0].late_sources[:2]
        checks.saved[second]=checks.saved[first]
        with pytest.raises(AssertionError,match='checkpoint distinct'):checks.arm_mixed()
    else:
        checks,_,_=relearned(PROGRAMS[0])
        if fault=='missing-step':checks.confidence_steps.pop()
        elif fault=='missing-main-update':checks.main_requests[0].pop()
        else:checks.last[1]['writes'][1]['bits']['counter']=6
        with pytest.raises(AssertionError):checks.pending()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('old-counter','wrong-identity','extra-service','missing-consumer'))
def test_final_service_and_consumers_still_required_after_correct_confidence_trajectory(fault):
    if fault=='missing-consumer':
        checks,_,_=completed(PROGRAMS[2]);del checks.consumers['serviced','neighbor']
        with pytest.raises(AssertionError,match='twelve'):checks.finish()
    else:
        checks,_,_=released(PROGRAMS[0]);value=deepcopy(checks.expected_plan[0][0])
        if fault=='old-counter':value['counter']=5
        elif fault=='wrong-identity':value['tag']^=1
        else:checks.write_accepted(0,transfer(100610,value))
        with pytest.raises(AssertionError):checks.write_accepted(0,transfer(100610,value))
    assert checks.coverage.groups['checked'].coverage==0
