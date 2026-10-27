"""Counterexamples have no DUT or hardware-coverage credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from bpuverify.sc.transaction.types import ScPrediction
from bpuverify.sc.model.eligibility import EligibilityProgram,FAMILIES
from bpuverify.sc.checker.original_enable import EnableChecks
from bpuverify.sc.coverage.original_enable import EnableCoverage

pytestmark=pytest.mark.toffee_functional_coverage(False)


def actual(expected):
    meta=deepcopy(expected['meta'])
    meta['debug']=deepcopy(expected['families'])
    return ScPrediction(expected['takens'][0],expected['useds'][0],meta,expected['takens'],expected['useds'])


def transfer(program,owner,sequence,tick,gate='eligible'):
    return NS(sequence_id=sequence,request=program.request(owner,gate),
              accepted_event=NS(tick=tick),completed_event=NS(tick=tick+2))


def prepared(direction=1,mode='serial'):
    program=EligibilityProgram(direction,mode)
    coverage=EnableCoverage(program)
    checks=EnableChecks(program,coverage)
    sequence=0
    for owner in program.owners:
        for _ in range(program.warm_votes):
            expected,_=program.expected(owner,'eligible',{})
            checks.cold_source(owner,transfer(program,owner,sequence,sequence*2),actual(expected),program.actual_input(owner))
            sequence+=1
    for source in tuple(checks.warm):
        checks.feedback(source)
        checks.accepted_feedback(source,40+source*2)
    checks.warm_complete()
    for probe in program.probes:
        expected,_=program.expected(probe.owner,probe.gate,checks.counts)
        spacing=2 if mode=='pipelined' else 8
        checks.query(probe,transfer(program,probe.owner,100+probe.ordinal,100+spacing*probe.ordinal,probe.gate),
                     actual(expected),program.actual_input(probe.owner,probe.gate))
    for ordinal,owner in enumerate(program.owners):
        expected,_=program.expected(owner,'eligible',checks.counts)
        checks.active_original(owner,transfer(program,owner,1000+ordinal,1000+4*ordinal),
                               actual(expected),program.actual_input(owner))
    return program,checks,coverage


def disabled_queries(program,checks,*,fault=None):
    for ordinal,owner in enumerate(program.owners):
        item=transfer(program,owner,1100+ordinal,1100+4*ordinal)
        witness=dict(program.actual_input(owner),enabled=False)
        prediction=ScPrediction(0,0,{'undefined_disabled_payload':owner.name},(0,)*10,(0,)*10)
        if fault=='wrong-enabled':witness['enabled']=True
        elif fault=='used-invalid':prediction=replace(prediction,useds=(1,)+(0,)*9)
        elif fault=='old-query':item=transfer(program,owner,1100+ordinal,900)
        elif fault=='wrong-owner':witness['pc']=program.owners[1-ordinal].pc
        checks.disabled_query(owner,item,prediction,witness)


def ignored_outcomes(program,checks):
    for ordinal,owner in enumerate(program.owners):
        before=dict(checks.counts)
        driven,expected=checks.old_feedback(owner)
        assert driven.pc==expected.pc==owner.pc
        assert driven.branches[0].actual_taken==1-owner.outcome
        checks.ignored_old_feedback(owner,1200+4*ordinal,actual_enabled=False)
        assert checks.counts==before


def restored_consumers(program,checks,*,fault=None):
    for ordinal,owner in enumerate(program.owners):
        expected,_=program.expected(owner,'eligible',checks.counts)
        prediction=actual(expected)
        witness=program.actual_input(owner)
        tick=1300+ordinal*4
        if fault=='wrong-enabled':witness['enabled']=False
        elif fault=='lost-learning':prediction=replace(prediction,useds=(0,*prediction.useds[1:]))
        elif fault=='wrong-direction':prediction=replace(prediction,takens=(1-owner.outcome,*prediction.takens[1:]))
        elif fault=='old-consumer':tick=1100
        checks.restored_consumer(owner,transfer(program,owner,1300+ordinal,tick),prediction,witness)


def positive_controls(program,checks,*,family_fault=None):
    sequence=2000
    for owner in program.owners:
        for step in range(1,program.reversal_steps(owner)+1):
            tick=2000+(sequence-2000)*8
            expected,_=program.expected(owner,'eligible',checks.counts,checks.reversals)
            checks.reverse_source(owner,transfer(program,owner,sequence,tick),actual(expected),program.actual_input(owner))
            checks.feedback(sequence,reverse=True)
            checks.accepted_feedback(sequence,tick+4,reverse=True)
            expected,_=program.expected(owner,'eligible',checks.counts,checks.reversals)
            prediction=actual(expected)
            if family_fault is not None:
                family,offset=family_fault
                weight=(program.warm_votes-step)*(1 if owner.outcome else -1)+offset
                prediction.meta['debug'][family]=(int(weight>=0),*prediction.meta['debug'][family][1:])
            checks.reverse_consumer(owner,transfer(program,owner,sequence+1,tick+6),prediction,program.actual_input(owner))
            sequence+=2


@pytest.mark.parametrize('direction',(0,1))
@pytest.mark.parametrize('mode',('serial','pipelined'))
def test_both_original_branches_survive_disable_and_only_fresh_enabled_controls_change_learning(direction,mode):
    program,checks,coverage=prepared(direction,mode)
    disabled_queries(program,checks)
    ignored_outcomes(program,checks)
    restored_consumers(program,checks)
    assert coverage.groups['checked'].coverage==0
    positive_controls(program,checks)
    checks.finish()
    assert len(checks.sources)==46 and len(checks.spent)==13
    assert checks.fresh_same_results=={'a','b'}
    assert coverage.groups['checked'].coverage==25.0
    with pytest.raises(AssertionError):checks.finish()


@pytest.mark.parametrize('fault',('wrong-enabled','used-invalid','old-query','wrong-owner'))
def test_disabled_query_requires_actual_gate_and_new_original_request(fault):
    program,checks,coverage=prepared()
    with pytest.raises(AssertionError):disabled_queries(program,checks,fault=fault)
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-source','unoffered','enabled-acceptance','stale-acceptance','acceptance-twice','feedback-twice','mutated-original'))
def test_old_outcome_is_real_once_and_actual_gate_is_checked_at_its_acceptance(fault):
    program,checks,coverage=prepared()
    disabled_queries(program,checks)
    owner=program.owners[0]
    if fault=='no-source':checks.old_sources.clear()
    if fault in ('no-source','unoffered'):
        with pytest.raises(AssertionError):checks.ignored_old_feedback(owner,1200,actual_enabled=False)
    elif fault=='mutated-original':
        checks.sources[1000][0].meta['tageCtr']=(0,0,0,0)
        with pytest.raises(AssertionError):checks.old_feedback(owner)
    else:
        checks.old_feedback(owner)
        if fault=='feedback-twice':
            with pytest.raises(AssertionError):checks.old_feedback(owner)
        elif fault=='acceptance-twice':
            checks.ignored_old_feedback(owner,1200,actual_enabled=False)
            with pytest.raises(AssertionError):checks.ignored_old_feedback(owner,1202,actual_enabled=False)
        else:
            with pytest.raises(AssertionError):checks.ignored_old_feedback(owner,
                1000 if fault=='stale-acceptance' else 1200,actual_enabled=fault=='enabled-acceptance')
    assert coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError):checks.finish()


@pytest.mark.parametrize('fault',('wrong-enabled','lost-learning','wrong-direction','old-consumer','missing-old-outcome','missing-disabled-query'))
def test_reopening_must_first_consume_the_original_unchanged_usable_state(fault):
    program,checks,coverage=prepared()
    disabled_queries(program,checks)
    ignored_outcomes(program,checks)
    if fault=='missing-old-outcome':checks.disabled_feedback.pop('b')
    elif fault=='missing-disabled-query':checks.disabled_queries.pop('b')
    with pytest.raises(AssertionError):restored_consumers(program,checks,fault=fault)
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('family',FAMILIES)
@pytest.mark.parametrize('offset',(-1,1))
def test_same_sign_corruption_during_disable_cannot_hide_behind_a_correct_reopened_direction(family,offset):
    program,checks,coverage=prepared()
    disabled_queries(program,checks)
    ignored_outcomes(program,checks)
    restored_consumers(program,checks)
    with pytest.raises(AssertionError):positive_controls(program,checks,family_fault=(family,offset))
    assert coverage.groups['checked'].coverage==0


def test_disabled_raw_metadata_is_neither_expected_nor_used_as_a_training_source():
    program,checks,coverage=prepared()
    disabled_queries(program,checks)
    assert all(checks.sources[record['source_id']][0].meta=={'undefined_disabled_payload':name}
               for name,record in checks.disabled_queries.items())
    ignored_outcomes(program,checks)
    assert all(record['source_id'] in (1000,1001) for record in checks.disabled_feedback.values())
    assert not {record['source_id'] for record in checks.disabled_queries.values()}&checks.spent
    assert coverage.groups['checked'].coverage==0
