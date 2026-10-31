"""Pure full-model event programs and adversarial actuals; no DUT credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest
from suites.frontend.bpu.bpu.model.tage.interior_prefix_learning import PROGRAMS,NEGATIVE,program,pending_states
from suites.frontend.bpu.bpu.model.tage.neighbor_migration import PC
from suites.frontend.bpu.bpu.model.tage.service import learning_inflight,pending_plan
from suites.frontend.bpu.bpu.checker.interior_prefix_learning import Checks
from suites.frontend.bpu.bpu.coverage.interior_prefix_learning import Coverage,RULES
from tests.bpu.scoreboard.direction_turnaround_fixtures import mixed,consumers
from tests.bpu.scoreboard.mixed_visibility_fixtures import packet
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_partial_reuse import transfer


def relearned(p,initial_pc=None):
    checks,reference,retired=mixed(p,checks_type=Checks,coverage_type=Coverage,initial_pc=initial_pc)
    model,event,_=reference;checks.arm_mixed();receipts=[];offers=[];commits=model.sources.tage.commits
    def advance(request=None):
        model.advance(replace(event,feedback=request))
        writes=model.sources.tage.offers.get((7,PC%4),())
        if writes:
            payload=[None,None]
            for write in writes:payload[write.way]=dict(row=write.row,valid=int(write.entry.valid),tag=write.entry.tag,counter=write.entry.counter)
            offers.append(tuple(payload))
    def matured():
        for _ in range(32):
            advance()
            if not learning_inflight(model.sources.tage):return
        raise AssertionError('independent complete-prefix learning did not mature')
    for index,(source,outcome) in enumerate(zip(checks.requests[3:],p.late_outcomes,strict=True)):
        tick=100400+index*(14 if p.schedule=='after-first-learning' else 2)
        request=resolution(source.token,outcome)
        assert not model.sources.feedback_for(request).reread
        checks.capture_state(NS(tick=tick),packet(checks,training=True))
        advance(request);receipts.append((tick,request))
        if p.schedule=='after-first-learning':
            matured()
            checks.capture_state(NS(tick=tick+8),packet(checks,index=3+index,plan=p.pending_before(index)))
            if index==0:
                assert pending_plan(model.sources.tage,7,PC%4)==checks.concrete(p.pending_after[0])
                checks.capture_state(NS(tick=tick+10),packet(checks,plan=p.pending_after[0]))
                checks.first_learning_settled(tick+10)
    if p.schedule=='adjacent-acceptance':
        matured()
        for index in range(2):checks.capture_state(NS(tick=100408+2*index),packet(checks,index=3+index,plan=p.pending_before(index)))
    assert offers==list(checks.expected_offers[3:])
    assert pending_plan(model.sources.tage,7,PC%4)==checks.concrete(p.final_plan)
    assert model.sources.tage.commits==commits
    checks.pipeline.last_resolution_controls=receipts[-1][0],event.enabled
    checks.accepted_burst(tuple(receipts));return checks,reference,retired


def completed(p,initial_pc=None):
    checks,reference,retired=relearned(p,initial_pc);checks.pending();consumers(checks,reference,'blocked')
    checks.pipeline.last_tick=100600;checks.release()
    for owner,versions in enumerate(checks.expected_plan):
        for index,payload in enumerate(versions):checks.write_accepted(owner,transfer(100610+2*index,payload))
    checks.services_complete();quiet(reference[0],reference[1]);consumers(checks,reference,'serviced')
    return checks,reference,retired


@pytest.mark.parametrize('initial_pc',(None,PC+0x40))
@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
def test_normal_preparation_complete_proposals_and_all_consumers_match_independent_reference(p,initial_pc):
    checks,_,_=completed(p,initial_pc)
    assert checks.prepared_sources[NEGATIVE] is checks.saved[NEGATIVE]
    assert checks.interior_source['profile'][0]==(0,0)
    assert tuple(provider[2] for provider in checks.interior_source['profile'][1])==(2,2)
    checks.finish();assert checks.coverage.groups['checked'].coverage==25
    assert len(checks.completed)==17 and len(checks.consumers)==12
    assert bool(checks.first_settled)==(p.schedule=='after-first-learning')


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
def test_declared_arithmetic_includes_earlier_executed_NT_even_when_current_value_holds(p):
    order=p.name.split('.')[0];assert p.pending_after==pending_states(order)
    assert p.final_plan==((('target-b',5),),(('target-a',0 if order=='positive-then-negative' else 1),('neighbor-b',6)))
    negative=p.late_sources.index(NEGATIVE)
    assert p.late_proposals[negative]==(('target-a',1),('target-b',1))
    assert all(not bad for outcome in p.late_outcomes for _,_,bad in outcome)


@pytest.mark.parametrize('p',(PROGRAMS[0],PROGRAMS[2]),ids=lambda p:p.name)
@pytest.mark.parametrize('fault',('missing-prefix-proposal','wrong-original-hint','wrong-pending-identity','extra-service','missing-consumer','mutated-original'))
def test_omitted_prefix_wrong_identity_or_final_counts_cannot_replace_full_learning(p,fault):
    if fault in ('missing-consumer','mutated-original'):
        checks,_,_=completed(p)
        if fault=='missing-consumer':del checks.consumers['serviced','neighbor']
        else:checks.requests[-1].meta.resolve['sequence']^=1
        with pytest.raises(AssertionError):checks.finish()
    elif fault in ('missing-prefix-proposal','wrong-original-hint'):
        checks,reference,_=mixed(p,checks_type=Checks,coverage_type=Coverage);checks.arm_mixed()
        for index,(s,outcome) in enumerate(zip(checks.requests[3:],p.late_outcomes,strict=True)):
            checks.capture_state(NS(tick=100400+2*index),packet(checks,training=True))
        index=p.late_sources.index(NEGATIVE);row=packet(checks,index=3+index,plan=p.pending_before(index))
        if index:
            checks.capture_state(NS(tick=100408),packet(checks,index=3,plan=p.pending_before(0)))
        if fault=='missing-prefix-proposal':row['state']['incoming'][0]['valid']=0
        else:row['state']['incoming'][0]['bits']['counter']=0
        checks.capture_state(NS(tick=100408+2*index),row)
        with pytest.raises(AssertionError):checks.raise_failure()
    else:
        checks,reference,_=relearned(p);checks.pending();consumers(checks,reference,'blocked')
        checks.pipeline.last_tick=100600;checks.release();value=deepcopy(checks.expected_plan[0][0])
        if fault=='extra-service':checks.write_accepted(0,transfer(100610,value))
        else:value['tag']^=1
        with pytest.raises(AssertionError):checks.write_accepted(0,transfer(100610,value))
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('missing',RULES)
def test_every_original_obligation_and_new_discriminator_is_required(missing):
    checks,_,_=completed(PROGRAMS[0])
    if missing!=RULES[7]:assert missing in checks.completed
    checks.completed.discard(missing)
    if missing==RULES[7]:checks.requests[-1].meta.resolve['sequence']^=1
    with pytest.raises(AssertionError):checks.finish()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.name)
def test_missing_actual_proposal_keeps_the_first_failure_and_zero_checked_credit(p):
    checks,_,_=relearned(p);checks.offered.pop()
    with pytest.raises(AssertionError) as first:checks.pending()
    with pytest.raises(AssertionError) as second:checks.finish()
    assert first.value is second.value and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('order,schedule',(('bank0','adjacent-acceptance'),('positive-then-negative','slot2'),(True,'after-first-learning'),('negative-then-positive',False)))
def test_physical_or_undeclared_profiles_do_not_create_extra_functional_bins(order,schedule):
    with pytest.raises(ValueError):program(order,schedule)


@pytest.mark.parametrize('fault',('accept-before-maturity','missing-maturity','proposal-before-maturity','requalified-maturity'))
def test_a_delay_label_cannot_replace_the_actual_first_learning_boundary(fault):
    checks,_,_=relearned(PROGRAMS[1]);settled=checks.first_settled['tick']
    with pytest.raises(AssertionError):
        if fault=='accept-before-maturity':checks.late_input_cadence(checks.input_ticks[3],settled)
        elif fault=='missing-maturity':
            checks.first_settled=None;checks.late_input_cadence(checks.input_ticks[3],checks.input_ticks[4])
        elif fault=='proposal-before-maturity':checks.late_proposal_cadence(4,settled)
        else:checks.first_learning_settled(settled)
    assert checks.coverage.groups['checked'].coverage==0
