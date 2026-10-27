"""Synthetic failures validate checking; they cannot contribute DUT coverage."""
from copy import deepcopy
from dataclasses import replace

import pytest

from bpuverify.bpu.coverage.owner_recency import OwnerRecencyCoverage
from bpuverify.bpu.model.tage.owner_recency import PROGRAMS
from bpuverify.bpu.model.tage.retouch_replacement import OwnerLearning
from tests.bpu.scoreboard.retouch_replacement_fixtures import learned,completed,packet
from tests.bpu.scoreboard.test_partial_reuse import transfer


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_all_owned_results_and_mixed_consumers_close_before_checked_credit(program):
    checks,_,retired=completed(program,coverage_factory=OwnerRecencyCoverage)
    assert checks.coverage.groups['checked'].coverage==0 and not retired
    checks.finish()
    assert all(g.coverage==100 for g in checks.coverage.groups.values())
    assert len(retired)==len(set(retired))
    assert tuple(map(len,checks.main))==program.main_update_counts


@pytest.mark.parametrize('initial_pc',(0x40000800,0x40000840))
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_two_models_agree_after_distinct_real_semantic_source_preparation(program,initial_pc):
    checks,_,_=learned(program,initial_pc=initial_pc,coverage_factory=OwnerRecencyCoverage)
    checks.pending()
    assert len(checks.effects)==len(program.feedback_order)


@pytest.mark.parametrize('fault',('invent-neighbor','wrong-owner','unprovided-counter','wrong-current-counter','both-ports-missing','auxiliary-invented'))
def test_absent_branch_is_not_a_dontcare_learning_obligation(fault):
    def corrupt(checks,phase,index,row):
        if phase!='proposal' or index!=4:return
        if fault=='invent-neighbor':
            row['state']['incoming'][1].update(valid=1,bits=dict(checks.keys[0][1],counter=7))
        elif fault=='wrong-owner':row['state']['incoming']=tuple(reversed(row['state']['incoming']))
        elif fault=='unprovided-counter':row['retained'][1][0]['counter']=0
        elif fault=='wrong-current-counter':row['state']['incoming'][0]['bits']['counter']=5
        elif fault=='both-ports-missing':row['state']['incoming'][0]['valid']=0
        else:row['main'][1]['direction']['valid']=1
    checks,_,_=learned(PROGRAMS[0],coverage_factory=OwnerRecencyCoverage,fault=corrupt)
    with pytest.raises(AssertionError):checks.pending()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('program',(PROGRAMS[0],PROGRAMS[1],*PROGRAMS[-2:]),ids=lambda p:p.name)
def test_insertion_only_or_global_paired_victim_cannot_pass_independent_accesses(program):
    def corrupt(checks,phase,index,row):
        if phase=='effect' and index==len(program.feedback_order)-1:
            legacy=packet(checks,program.trace(policy='insertion')[-1])
            row['retained']=legacy['retained'];row['state']['writes']=legacy['state']['writes']
    checks,_,_=learned(program,coverage_factory=OwnerRecencyCoverage,fault=corrupt)
    with pytest.raises(AssertionError):checks.pending()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('program',PROGRAMS[:2],ids=lambda p:p.name)
def test_refreshing_unprovided_owner_is_rejected_even_if_all_its_counters_are_unchanged(program):
    def corrupt(checks,phase,index,row):
        if phase!='effect' or index!=len(program.feedback_order)-1:return
        provided=program.retouches[0][1];untouched=1-provided
        snapshot=list(checks.trace[-1]);wrong=list(checks.trace[-2][untouched])
        # Only the later eviction is wrong. The unprovided owner's earlier
        # counters and every other retained payload remain exactly unchanged.
        rank=next(i for i,r in enumerate(wrong) if r.history==program.victims[provided])
        wrong[rank]=OwnerLearning(4,program.initial_counters(4)[untouched]+(1 if untouched else -1))
        snapshot[untouched]=tuple(wrong)
        actual=packet(checks,tuple(snapshot))
        row['retained']=actual['retained'];row['state']['writes']=actual['state']['writes']
    checks,_,_=learned(program,coverage_factory=OwnerRecencyCoverage,fault=corrupt)
    with pytest.raises(AssertionError,match='complete owned version'):checks.pending()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-final-consumer','missing-survivor-service','extra-untouched-service'))
def test_same_total_count_cannot_hide_wrong_branch_visibility_or_service(fault):
    checks,_,_=completed(PROGRAMS[0],coverage_factory=OwnerRecencyCoverage)
    if fault=='missing-final-consumer':checks.new_sources.pop(next(iter(checks.new_sources)))
    elif fault=='missing-survivor-service':checks.written[1].pop()
    else:
        with pytest.raises(AssertionError):checks.write_accepted(1,transfer(1800,checks.expected_plan[1][0]))
    with pytest.raises(AssertionError):checks.finish()
    assert checks.coverage.groups['checked'].coverage==0


def test_unreviewed_physical_coordinate_cannot_expand_semantic_program_universe():
    with pytest.raises(ValueError):OwnerRecencyCoverage(replace(PROGRAMS[0],name='physical-slot-2'))
