"""Independent original-source rejection and corruption controls, no DUT credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from bpuverify.sc.transaction.types import ScPrediction
from bpuverify.sc.model.eligibility import FAMILIES,GATES
from bpuverify.sc.model.original_feedback import FeedbackProgram,expected_offer
from bpuverify.sc.checker.original_feedback import FeedbackChecks
from bpuverify.sc.coverage.original_feedback import FeedbackCoverage,PROFILES

pytestmark=pytest.mark.toffee_functional_coverage(False)


def actual(expected):
    meta=deepcopy(expected['meta'])
    meta['debug']=deepcopy(expected['families'])
    return ScPrediction(expected['takens'][0],expected['useds'][0],meta,expected['takens'],expected['useds'])


def transfer(program,owner,gate,sequence,tick):
    return NS(sequence_id=sequence,request=program.request(owner,gate),
              accepted_event=NS(tick=tick),completed_event=NS(tick=tick+2))


def prepared(gate='provider-missing',direction=1,mode='serial'):
    program=FeedbackProgram(direction,mode,gate)
    coverage=FeedbackCoverage(program)
    checks=FeedbackChecks(program,coverage)
    sequence=0
    for owner in program.owners:
        for _ in range(program.warm_votes):
            expected,_=program.expected(owner,'eligible',{})
            checks.cold_source(owner,transfer(program,owner,'eligible',sequence,sequence*2),actual(expected),program.actual_input(owner))
            sequence+=1
    for source in tuple(checks.warm):
        checks.feedback(source)
        checks.accepted_feedback(source,40+source*2)
    checks.warm_complete()
    for probe in program.probes:
        expected,_=program.expected(probe.owner,probe.gate,checks.counts)
        spacing=2 if mode=='pipelined' else 8
        checks.query(probe,transfer(program,probe.owner,probe.gate,100+probe.ordinal,100+spacing*probe.ordinal),
            actual(expected),program.actual_input(probe.owner,probe.gate))
    return program,checks,coverage


def rejected_sources(program,checks,*,fault=None):
    for ordinal,owner in enumerate(program.owners):
        source_id,tick=1000+2*ordinal,1000+12*ordinal
        gate=program.rejection_gate
        expected,_=program.expected(owner,gate,checks.counts)
        checks.rejected_source(owner,transfer(program,owner,gate,source_id,tick),actual(expected),program.actual_input(owner,gate))
        before=dict(checks.counts)
        driven,expected_feedback=checks.rejected_feedback(owner)
        assert driven.pc==expected_feedback.pc==owner.pc
        assert len(driven.branches)==1 and driven.branches[0].actual_taken==program.feedback_outcome(owner)
        checks.accepted_rejection(owner,tick+4)
        assert checks.counts==before
        expected,_=program.expected(owner,'eligible',checks.counts)
        prediction=actual(expected)
        if fault=='lost-learning':prediction=replace(prediction,useds=(0,*prediction.useds[1:]))
        elif fault=='wrong-direction':prediction=replace(prediction,takens=(1-owner.outcome,*prediction.takens[1:]))
        checks.retained_consumer(owner,transfer(program,owner,'eligible',source_id+1,tick+4 if fault=='stale-consumer' else tick+6),
            prediction,program.actual_input(owner))


def reverse_sources(program,checks,*,family_fault=None):
    sequence=2000
    for owner in program.owners:
        for step in range(1,program.reversal_steps(owner)+1):
            tick=2000+(sequence-2000)*8
            expected,_=program.expected(owner,'eligible',checks.counts,checks.reversals)
            checks.reverse_source(owner,transfer(program,owner,'eligible',sequence,tick),actual(expected),program.actual_input(owner))
            checks.feedback(sequence,reverse=True)
            checks.accepted_feedback(sequence,tick+4,reverse=True)
            expected,_=program.expected(owner,'eligible',checks.counts,checks.reversals)
            prediction=actual(expected)
            if family_fault is not None:
                family,offset=family_fault
                weight=(3-step)*(1 if owner.outcome else -1)+offset
                prediction.meta['debug'][family]=(int(weight>=0),*prediction.meta['debug'][family][1:])
            checks.reverse_consumer(owner,transfer(program,owner,'eligible',sequence+1,tick+6),prediction,program.actual_input(owner))
            sequence+=2


@pytest.mark.parametrize('gate',GATES)
@pytest.mark.parametrize('direction',(0,1))
@pytest.mark.parametrize('mode',('serial','pipelined'))
def test_complete_single_cause_lifetime_retains_then_reverses_each_independent_original_branch(gate,direction,mode):
    program,checks,coverage=prepared(gate,direction,mode)
    rejected_sources(program,checks)
    assert coverage.groups['checked'].coverage==0
    reverse_sources(program,checks)
    checks.finish()
    assert len(checks.sources)==54 and len(checks.spent)==19
    assert len(checks.rejected_acceptances)==len(checks.rejected_consumers)==2
    assert coverage.groups['checked'].coverage==pytest.approx(100/len(PROFILES))
    with pytest.raises(AssertionError):checks.finish()


@pytest.mark.parametrize('gate',GATES)
@pytest.mark.parametrize('direction',(0,1))
def test_independent_complete_feedback_offer_proves_which_source_qualification_is_absent(gate,direction):
    program=FeedbackProgram(direction,'serial',gate)
    counts={owner.name:3 for owner in program.owners}
    for owner in program.owners:
        expected,_=program.expected(owner,gate,counts)
        feedback=program.rejected_feedback(owner,expected['meta'])
        offer=expected_offer(feedback,branch_count=8,fold_count=19)
        branch=offer['branches'][0]
        original=offer['mbtb_meta'][0][0]
        assert original['rawHit']==int(gate!='main-miss')
        assert branch['branch_type']==original['attribute']['branchType']==(2 if gate=='nonconditional' else 1)
        assert offer['meta']['tagePredValid'][0]==int(gate!='provider-missing')
        assert branch['taken']==program.feedback_outcome(owner) and branch['position']==owner.first_position
        assert all(not item['valid'] for item in offer['branches'][1:])


@pytest.mark.parametrize('gate',GATES)
@pytest.mark.parametrize('fault',('wrong-cause-input','stale-original','duplicate-original','metadata-mutated','unoffered-acceptance','duplicate-feedback','duplicate-acceptance'))
def test_ignored_outcome_requires_a_fresh_original_and_one_real_acceptance(gate,fault):
    program,checks,coverage=prepared(gate)
    owner=program.owners[0]
    expected,_=program.expected(owner,gate,checks.counts)
    item=transfer(program,owner,gate,1000,1000)
    witness=program.actual_input(owner,gate)
    if fault=='wrong-cause-input':
        witness=program.actual_input(owner,next(other for other in GATES if other!=gate))
    if fault in ('wrong-cause-input','stale-original'):
        if fault=='stale-original':item=transfer(program,owner,gate,1000,50)
        with pytest.raises(AssertionError):checks.rejected_source(owner,item,actual(expected),witness)
    else:
        checks.rejected_source(owner,item,actual(expected),witness)
        if fault=='duplicate-original':
            with pytest.raises(AssertionError):checks.rejected_source(owner,item,actual(expected),witness)
        elif fault=='metadata-mutated':
            checks.sources[1000][0].meta['tagePredValid']=(0,0,0,0) if gate!='provider-missing' else (1,1,1,1)
            with pytest.raises(AssertionError):checks.rejected_feedback(owner)
        elif fault=='unoffered-acceptance':
            with pytest.raises(AssertionError):checks.accepted_rejection(owner,1004)
        else:
            checks.rejected_feedback(owner)
            if fault=='duplicate-feedback':
                with pytest.raises(AssertionError):checks.rejected_feedback(owner)
            else:
                checks.accepted_rejection(owner,1004)
                with pytest.raises(AssertionError):checks.accepted_rejection(owner,1006)
    assert coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError):checks.finish()


@pytest.mark.parametrize('gate',GATES)
@pytest.mark.parametrize('fault',('lost-learning','wrong-direction','stale-consumer'))
def test_fresh_consumer_must_preserve_the_original_usable_correction(gate,fault):
    program,checks,coverage=prepared(gate)
    with pytest.raises(AssertionError):rejected_sources(program,checks,fault=fault)
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('gate',GATES)
@pytest.mark.parametrize('family',FAMILIES)
@pytest.mark.parametrize('offset',(-1,1))
def test_same_sign_single_family_damage_after_one_rejection_is_not_hidden_by_public_direction(gate,family,offset):
    program,checks,coverage=prepared(gate)
    rejected_sources(program,checks)
    with pytest.raises(AssertionError):reverse_sources(program,checks,family_fault=(family,offset))
    assert coverage.groups['checked'].coverage==0


def test_missing_actual_original_has_a_scoreboard_failure_not_a_key_error():
    program,checks,coverage=prepared()
    with pytest.raises(AssertionError):checks.accepted_rejection(program.owners[0],1004)
    assert coverage.groups['checked'].coverage==0


def test_nonconditional_direct_feedback_is_taken_and_still_challenges_one_real_negative_identity():
    program=FeedbackProgram(1,'serial','nonconditional')
    outcomes={owner.name:program.feedback_outcome(owner) for owner in program.owners}
    assert outcomes=={'a':1,'b':1}
    assert sum(program.feedback_outcome(owner)!=owner.outcome for owner in program.owners)==1


@pytest.mark.parametrize('gate',('unknown','queued','ready-valid'))
def test_rejection_cause_is_explicit_semantics_not_a_protocol_or_queue_label(gate):
    with pytest.raises(ValueError):FeedbackProgram(1,'serial',gate)
