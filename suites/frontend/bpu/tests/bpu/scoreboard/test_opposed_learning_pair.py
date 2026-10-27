"""Independent arithmetic, full source lifetimes and adversarial actuals."""
from copy import deepcopy
import pytest
from bpuverify.bpu.model.tage.opposed_learning_pair import PROGRAMS,ORDERS,BOUNDARIES,program,pending_states
from bpuverify.bpu.model.tage.neighbor_migration import PC
from bpuverify.bpu.checker.opposed_learning_pair import OpposedLearningPairChecks
from bpuverify.bpu.coverage.opposed_learning_pair import Coverage
from tests.bpu.scoreboard.test_direction_turnaround_model import (
    test_reversed_outcomes_use_each_current_version_and_preserve_all_unrelated_histories as check_reference_program)
from tests.bpu.scoreboard.direction_turnaround_fixtures import completed,relearned,released
from tests.bpu.scoreboard.test_partial_reuse import transfer

OPTIONS=dict(checks_type=OpposedLearningPairChecks,coverage_type=Coverage)


@pytest.mark.parametrize('initial_pc',(None,PC+0x40))
@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
def test_two_original_epochs_are_correct_and_both_current_effects_survive(p,initial_pc):
    check_reference_program(p,initial_pc)


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
def test_complete_services_and_all_twelve_consumers_close_only_this_profile(p):
    checks,_,_=completed(p,**OPTIONS)
    assert checks.coverage.groups['checked'].coverage==0
    checks.finish();snapshot=checks.snapshot()
    assert checks.coverage.groups['checked'].coverage==12.5
    assert snapshot['closed'] and snapshot['phase']=='consuming'
    assert len(snapshot['accepted_ticks'])==len(snapshot['actual_proposals'])==5
    assert len(snapshot['consumer_profiles'])==12
    assert len(snapshot['completed_obligations'])==15
    assert not snapshot['full_FTQ_source_eligibility_proved']
    with pytest.raises(AssertionError,match='single-use'):checks.finish()


@pytest.mark.parametrize('p',(PROGRAMS[0],PROGRAMS[4]),ids=lambda p:p.name)
@pytest.mark.parametrize('fault',('stale-current-counter','wrong-identity','extra-service','before-release','missing-final-consumer','mutated-original'))
def test_neither_final_counts_nor_original_hint_can_replace_a_complete_actual_lifetime(p,fault):
    if fault in ('missing-final-consumer','mutated-original'):
        checks,_,_=completed(p,**OPTIONS)
        if fault=='missing-final-consumer':del checks.consumers['serviced','neighbor']
        else:checks.requests[-1].meta.resolve['sequence']^=1
        with pytest.raises(AssertionError):checks.finish()
    else:
        checks,_,_=released(p,**OPTIONS)
        value=deepcopy(checks.expected_plan[0][0]);tick=100610
        if fault=='stale-current-counter':value['counter']=1
        elif fault=='wrong-identity':value['tag']^=1
        elif fault=='before-release':tick=checks.release_tick
        else:checks.write_accepted(0,transfer(tick,deepcopy(value)))
        with pytest.raises(AssertionError):checks.write_accepted(0,transfer(tick,value))
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
def test_second_accepted_input_without_its_proposal_is_not_success(p):
    checks,_,_=relearned(p,missing_last=True,**OPTIONS)
    with pytest.raises(AssertionError,match='all complete actual proposals') as first:checks.pending()
    with pytest.raises(AssertionError) as second:checks.finish()
    assert first.value is second.value
    assert checks.coverage.groups['checked'].coverage==0
    assert checks.snapshot()['first_failure']


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
def test_declarative_arithmetic_keeps_neighbor_and_does_not_assume_Main_commutes(p):
    order,boundary=p.name.split('.')
    assert order in ORDERS and boundary in BOUNDARIES
    a=0 if order==ORDERS[0] else 1
    assert p.target_counters==(a,5) and p.neighbor_counters==(1,6)
    assert p.final_plan==((('target-b',5),),(('target-a',a),('neighbor-b',6)))
    assert p.main_counters==((0,0) if order==ORDERS[0] else (3,0))
    assert p.pending_after==pending_states(order)
    assert len(set(p.late_sources))==2 and all(not bad for outcome in p.late_outcomes for _,_,bad in outcome)


@pytest.mark.parametrize('order,boundary',(('physical-port-0','both-interior'),('positive-then-negative','slot3'),(True,'both-interior'),('negative-then-positive',False)))
def test_physical_or_undeclared_profiles_cannot_create_bins(order,boundary):
    with pytest.raises(ValueError):program(order,boundary)
