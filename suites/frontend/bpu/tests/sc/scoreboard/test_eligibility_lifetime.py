"""Independent expectation and corruption tests; no native DUT credit."""
import ast
import inspect
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

# Match the production adapter's public policy for scoreboard/model tests.
# This isolated runner deliberately does not load the project test-area hook.
pytestmark=pytest.mark.toffee_functional_coverage(False)

from suites.frontend.bpu.sc.transaction.types import ScPrediction
from suites.frontend.bpu.sc.model.eligibility import EligibilityProgram,GATES,RULES,FAMILIES
from suites.frontend.bpu.sc.checker.eligibility import EligibilityChecks
from suites.frontend.bpu.sc.coverage.eligibility import EligibilityCoverage
from suites.frontend.bpu.sc.monitor.eligibility import InputWitnessLedger


def actual(expected):
    meta=deepcopy(expected['meta'])
    meta['debug']=deepcopy(expected['families'])
    return ScPrediction(expected['takens'][0],expected['useds'][0],meta,expected['takens'],expected['useds'])


def transfer(program,owner,gate,sequence,tick):
    return NS(sequence_id=sequence,request=program.request(owner,gate),
        accepted_event=NS(tick=tick),completed_event=NS(tick=tick+2))


def prepared(direction=1,mode='serial'):
    program=EligibilityProgram(direction,mode)
    coverage=EligibilityCoverage(program)
    checks=EligibilityChecks(program,coverage)
    sequence=0
    for owner in program.owners:
        for _ in range(program.warm_votes):
            expected,_=program.expected(owner,'eligible',{})
            item=transfer(program,owner,'eligible',sequence,sequence*2)
            checks.cold_source(owner,item,actual(expected),program.actual_input(owner))
            sequence+=1
    for source in tuple(checks.warm):
        checks.feedback(source)
        checks.accepted_feedback(source,40+source*2)
    checks.warm_complete()
    return program,checks,coverage


def all_queries(program,checks,*,spacing=None):
    spacing=(2 if program.mode=='pipelined' else 8) if spacing is None else spacing
    for probe in program.probes:
        expected,_=program.expected(probe.owner,probe.gate,checks.counts)
        checks.query(probe,transfer(program,probe.owner,probe.gate,100+probe.ordinal,100+spacing*probe.ordinal),
            actual(expected),program.actual_input(probe.owner,probe.gate))


def reverse_lifetime(program,checks,*,family_fault=None,stale_consumer=False):
    sequence=1000
    for owner in program.owners:
        for step in range(1,program.reversal_steps(owner)+1):
            tick=1000+(sequence-1000)*8
            expected,_=program.expected(owner,'eligible',checks.counts,checks.reversals)
            item=transfer(program,owner,'eligible',sequence,tick)
            checks.reverse_source(owner,item,actual(expected),program.actual_input(owner))
            checks.feedback(sequence,reverse=True)
            checks.accepted_feedback(sequence,tick+4,reverse=True)
            expected,_=program.expected(owner,'eligible',checks.counts,checks.reversals)
            prediction=actual(expected)
            if family_fault is not None:
                family,offset=family_fault
                weight=(program.warm_votes-step)*(1 if owner.outcome else -1)+offset
                prediction.meta['debug'][family]=(int(weight>=0),*prediction.meta['debug'][family][1:])
            consumer=transfer(program,owner,'eligible',sequence+1,tick+4 if stale_consumer else tick+6)
            checks.reverse_consumer(owner,consumer,prediction,program.actual_input(owner))
            sequence+=2


@pytest.mark.parametrize('direction',(0,1))
@pytest.mark.parametrize('mode',('serial','pipelined'))
def test_minimal_qualified_votes_make_both_polarities_strong_even_without_trained_bias(direction,mode):
    program=EligibilityProgram(direction,mode)
    assert program.warm_votes==2
    counts={owner.name:program.warm_votes for owner in program.owners}
    program.require_strong_warm_state(counts)
    for owner in program.owners:
        normal,scores=program.expected(owner,'eligible',counts)
        lost,lost_scores=program.expected(owner,'provider-missing',counts)
        assert normal['useds']==(1,)+(0,)*9 and lost['useds']==(0,)*10
        assert normal['takens'][0]==lost['takens'][0]==owner.outcome
        assert scores[0] in (40,-24) and lost_scores[0] in (36,-20)
    deficient={owner.name:program.warm_votes-1 for owner in program.owners}
    with pytest.raises(AssertionError):program.require_strong_warm_state(deficient)


@pytest.mark.parametrize('gate',GATES)
@pytest.mark.parametrize('direction',(0,1))
def test_ineligible_source_is_rejected_despite_strong_preexisting_statistics_and_restores_without_learning(gate,direction):
    program=EligibilityProgram(direction,'serial')
    counts={owner.name:program.warm_votes for owner in program.owners}
    for owner in program.owners:
        before=program.expected(owner,'eligible',counts)
        rejected,_=program.expected(owner,gate,counts)
        assert rejected['useds'][0]==0
        assert rejected['meta']['sumAboveThres'][0]==1
        assert before==program.expected(owner,'eligible',counts)
        assert rejected['meta']['tagePredValid'][0]==int(gate!='provider-missing')


@pytest.mark.parametrize('fault',('bad-direction','bad-mode','foreign-owner','excess-votes'))
def test_invalid_program_inputs_are_not_silently_coerced(fault):
    program=EligibilityProgram(1,'serial')
    with pytest.raises(ValueError):
        if fault=='bad-direction':EligibilityProgram(True,'serial')
        elif fault=='bad-mode':EligibilityProgram(1,'queued')
        elif fault=='foreign-owner':program.request(replace(program.owners[0],pc=0))
        else:program.thresholds({'a':4,'b':3})


@pytest.mark.parametrize('fault',('none','wrong-qualifier','borrowed-provider','wrong-counter','wrong-pc'))
def test_input_witness_distinguishes_gate_causes_even_when_public_use_bits_match(fault):
    program,checks,coverage=prepared()
    owner=program.owners[0]
    probe=next(p for p in program.probes if p.owner==owner and p.gate=='main-miss')
    expected,_=program.expected(owner,probe.gate,checks.counts)
    item=transfer(program,owner,probe.gate,100,100)
    witness=program.actual_input(owner,probe.gate)
    if fault=='wrong-qualifier':witness=program.actual_input(owner,'nonconditional')
    elif fault=='borrowed-provider':witness['branches']=(replace(witness['branches'][0],provider_valid=0),*witness['branches'][1:])
    elif fault=='wrong-counter':witness['branches']=(replace(witness['branches'][0],tage_counter=3),*witness['branches'][1:])
    elif fault=='wrong-pc':witness['pc']=program.owners[1].pc
    if fault=='none':checks.query(probe,item,actual(expected),witness)
    else:
        with pytest.raises(AssertionError):checks.query(probe,item,actual(expected),witness)
        assert not checks.queries
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('used-invalid','lost-learning','wrong-owner-meta','wrong-family'))
def test_incorrect_public_correction_or_restoration_raises_with_no_checked_credit(fault):
    program,checks,coverage=prepared(direction=0)
    probe=next(p for p in program.probes if p.gate=='provider-missing') if fault=='used-invalid' else program.probes[0]
    owner=probe.owner
    expected,_=program.expected(owner,probe.gate,checks.counts)
    prediction=actual(expected)
    if fault in ('used-invalid','lost-learning'):
        used=(1 if fault=='used-invalid' else 0,*prediction.useds[1:])
        prediction=replace(prediction,useds=used)
    elif fault=='wrong-owner-meta':prediction.meta['tageCtr']=(4,)*4
    else:prediction.meta['debug']['scPathTakenVec']=(1,)*4
    with pytest.raises(AssertionError):
        checks.query(probe,transfer(program,owner,probe.gate,100,100),prediction,program.actual_input(owner,probe.gate))
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('none','missing-query','duplicate-query','original-mutated','not-pipelined','serial-overlap'))
def test_only_complete_original_lifetimes_and_real_cadence_acquire_checked_credit(fault):
    mode='pipelined' if fault=='not-pipelined' else 'serial'
    program,checks,coverage=prepared(mode=mode)
    probes=program.probes[:-1] if fault=='missing-query' else program.probes
    spacing=2 if fault=='serial-overlap' else 8
    last=None
    for probe in probes:
        expected,_=program.expected(probe.owner,probe.gate,checks.counts)
        item=transfer(program,probe.owner,probe.gate,100+probe.ordinal,100+spacing*probe.ordinal)
        checks.query(probe,item,actual(expected),program.actual_input(probe.owner,probe.gate))
        last=probe,item,actual(expected),program.actual_input(probe.owner,probe.gate)
    if fault=='duplicate-query':
        with pytest.raises(AssertionError):checks.query(*last)
    elif fault=='original-mutated':checks.sources[0][0].meta['tageCtr']=(0,)*4
    if fault=='none':
        reverse_lifetime(program,checks)
        checks.finish()
        assert coverage.groups['checked'].coverage==25.0
        assert len(checks.queries)==22 and len(checks.sources)==40
        assert len(checks.spent)==11
    else:
        with pytest.raises(AssertionError):checks.finish()
        assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('direction',(0,1))
@pytest.mark.parametrize('mode',('serial','pipelined'))
def test_both_submission_modes_and_polarity_orders_complete_the_same_semantic_lifetime(direction,mode):
    program,checks,coverage=prepared(direction=direction,mode=mode)
    all_queries(program,checks)
    reverse_lifetime(program,checks)
    checks.finish()
    assert coverage.groups['checked'].coverage==25.0


@pytest.mark.parametrize('fault',('feedback-twice','acceptance-twice','stale-acceptance','duplicate-original','late-original'))
def test_warm_sources_cannot_be_reused_or_replaced_by_a_stale_acceptance(fault):
    program,checks,coverage=prepared()
    if fault=='feedback-twice':
        with pytest.raises(AssertionError):checks.feedback(0)
    elif fault=='acceptance-twice':
        with pytest.raises(AssertionError):checks.accepted_feedback(0,80)
    elif fault=='stale-acceptance':
        checks.accepted_feedback_ids.remove(0)
        with pytest.raises(AssertionError):checks.accepted_feedback(0,0)
    elif fault=='late-original':
        owner=program.owners[0]
        expected,_=program.expected(owner,'eligible',{})
        with pytest.raises(AssertionError):checks.cold_source(owner,transfer(program,owner,'eligible',100,100),
            actual(expected),program.actual_input(owner))
    else:
        checks=EligibilityChecks(program,coverage)
        owner=program.owners[0]
        expected,_=program.expected(owner,'eligible',{})
        item=transfer(program,owner,'eligible',0,0)
        checks.cold_source(owner,item,actual(expected),program.actual_input(owner))
        with pytest.raises(AssertionError):
            checks.cold_source(owner,item,actual(expected),program.actual_input(owner))
    assert coverage.groups['checked'].coverage==0


def test_expectation_is_separate_from_cycle_model_and_signal_interfaces():
    tree=ast.parse(Path(inspect.getfile(EligibilityProgram)).read_text())
    names={node.id for node in ast.walk(tree) if isinstance(node,ast.Name)}
    assert not names&{'ScReference','ScSemanticChecker','dut','get_','set_','RisingEdge','FallingEdge'}
    assert len(RULES)==8


@pytest.mark.parametrize('direction',(0,1))
def test_exact_opposite_outcomes_cross_all_family_signs_then_override_the_unchanged_base(direction):
    program=EligibilityProgram(direction,'serial')
    counts={owner.name:2 for owner in program.owners}
    for owner in program.owners:
        steps=4 if owner.outcome else 3
        assert program.reversal_steps(owner)==steps
        for step in range(1,steps+1):
            expected,scores=program.expected(owner,'eligible',counts,{owner.name:step})
            weight=(2-step)*(1 if owner.outcome else -1)
            assert scores[0]==8*(2*weight+1)
            assert all(expected['families'][family][0]==int(weight>=0) for family in FAMILIES)
            if step==steps:
                assert expected['useds'][0]==1 and expected['takens'][0]==1-owner.outcome
                assert program.thresholds(counts,{owner.name:step})[(owner.first_position%8)^(owner.first_position//8)]==(1130 if owner.outcome else 1133)


@pytest.mark.parametrize('direction',(0,1))
@pytest.mark.parametrize('family',FAMILIES)
@pytest.mark.parametrize('offset',(-1,1))
def test_single_family_same_sign_damage_cannot_hide_behind_equal_warm_public_direction(direction,family,offset):
    program,checks,coverage=prepared(direction=direction)
    all_queries(program,checks)
    owner=program.owners[0]
    assert int((3*(1 if owner.outcome else -1)+offset)>=0)==owner.outcome
    with pytest.raises(AssertionError):
        reverse_lifetime(program,checks,family_fault=(family,offset))
    assert coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError):checks.finish()


def test_reverse_consumer_cannot_be_an_old_or_same_boundary_prediction():
    program,checks,coverage=prepared()
    all_queries(program,checks)
    with pytest.raises(AssertionError):reverse_lifetime(program,checks,stale_consumer=True)
    assert coverage.groups['checked'].coverage==0


def test_all_cold_sources_must_respond_before_the_first_warm_feedback():
    program=EligibilityProgram(1,'serial')
    coverage=EligibilityCoverage(program)
    checks=EligibilityChecks(program,coverage)
    owner=program.owners[0]
    expected,_=program.expected(owner,'eligible',{})
    for sequence,tick in ((0,10),(1,20)):
        checks.cold_source(owner,transfer(program,owner,'eligible',sequence,tick),actual(expected),program.actual_input(owner))
    checks.feedback(0)
    with pytest.raises(AssertionError):checks.accepted_feedback(0,15)
    assert coverage.groups['checked'].coverage==0


def test_passive_input_witness_owns_pc_history_and_qualifiers_without_reference_outputs():
    ledger=InputWitnessLedger()
    context=NS(path=3,global_history=5,backward=1,loop=7,common_valid=True)
    def event(**changes):
        return NS(**(dict(reset=False,ready=True,pc=None,context=context,advance=False,select=False,
                          branches=(),enabled=True)|changes))
    ledger.capture_input(NS(tick=0),event(pc=17))
    ledger.capture_input(NS(tick=2),event(pc=29,advance=True))
    ledger.capture_input(NS(tick=4),event(advance=True,select=True,branches=('original-base',)))
    witness=ledger.input_for(NS(completed_event=NS(tick=5)))
    assert witness==dict(pc=17,enabled=True,history=(3,5,1,7,True),branches=('original-base',))
    ledger.capture_output(NS(tick=5),dict(pc='not-an-input',weights='never-consumed'))
    assert ledger.input_for(NS(completed_event=NS(tick=5)))==witness
    ledger.capture_input(NS(tick=6),event(select=True,branches=('younger-base',),enabled=False))
    assert ledger.input_for(NS(completed_event=NS(tick=7)))['pc']==29
    ledger.capture_input(NS(tick=8),event(reset=True))
    with pytest.raises(AssertionError):ledger.input_for(NS(completed_event=NS(tick=5)))


def test_input_witness_rejects_selection_without_an_actual_original_pc():
    ledger=InputWitnessLedger()
    ledger.capture_input(NS(tick=0),NS(reset=False,ready=True,select=True))
    with pytest.raises(AssertionError):ledger.input_for(NS(completed_event=NS(tick=1)))
