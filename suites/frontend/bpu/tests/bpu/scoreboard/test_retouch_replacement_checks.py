"""Policy, source, counter, service and consumer mistakes must remain visible."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from bpuverify.bpu.model.tage.retouch_replacement import PROGRAMS
from bpuverify.bpu.coverage.retouch_replacement import RetouchReplacementCoverage
from tests.bpu.scoreboard.retouch_replacement_fixtures import prepared,learned,released,completed,packet,consumers
from tests.bpu.scoreboard.test_partial_reuse import transfer


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_ten_obligations_need_all_versions_eight_real_services_and_ten_consumers(program):
    checks,_,retired=completed(program)
    assert checks.coverage.groups['checked'].coverage==0 and not retired
    checks.finish();assert all(g.coverage==100 for g in checks.coverage.groups.values())
    assert len(retired)==len(set(retired))
    with pytest.raises(AssertionError,match='single-use'):checks.finish()


@pytest.mark.parametrize('initial_pc',(0x40000800,0x40000840))
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_two_semantic_models_agree_after_normal_source_preparation_and_learning(program,initial_pc):
    checks,_,_=learned(program,initial_pc=initial_pc);checks.pending()
    assert len(checks.effects)==len(program.feedback_order)
    assert len({id(s.token.history) for s in checks.sources})==len(checks.sources)


@pytest.mark.parametrize('fault',('old-seed-over-current','wrong-tag','wrong-owner','dropped-neighbor','early-service','reread','missing-input'))
def test_bad_actual_learning_is_not_repaired_from_reference_state(fault):
    def corrupt(checks,phase,index,row):
        if phase!='proposal' or index!=4:return
        if fault=='old-seed-over-current':row['state']['incoming'][0]['bits']['counter']=7
        elif fault=='wrong-tag':row['state']['incoming'][0]['bits']['tag']^=1
        elif fault=='wrong-owner':row['state']['incoming']=tuple(reversed(row['state']['incoming']))
        elif fault=='dropped-neighbor':row['retained'][0][1]['counter']^=1
        elif fault=='early-service':row['state']['writes'][0]['ready']=1
        elif fault=='reread':row['state']['reads'][1]['valid']=1
        else:row['state']['incoming'][0]['valid']=0
    checks,_,_=learned(PROGRAMS[0],fault=corrupt)
    with pytest.raises(AssertionError) as first:checks.pending()
    with pytest.raises(AssertionError) as second:checks.finish()
    assert first.value is second.value and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('program',PROGRAMS[:3],ids=lambda p:p.name)
def test_insertion_only_hardware_shape_cannot_pass_learning_recency_contract(program):
    def fault(checks,phase,index,row):
        if phase=='effect' and index==len(program.feedback_order)-1:
            legacy=packet(checks,program.trace(policy='insertion')[-1])
            row['retained']=legacy['retained']
            row['state']['dirty']=legacy['state']['dirty']
            row['state']['writes']=legacy['state']['writes']
    checks,_,_=learned(program,fault=fault)
    with pytest.raises(AssertionError):checks.pending()
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('stale-fold','unexpected-main-drop'))
def test_real_admission_preconditions_are_not_inferred_from_buffer_fullness(fault):
    checks,_,_=prepared(PROGRAMS[0]);row=packet(checks,(None,)*4,input_index=0)
    if fault=='stale-fold':
        values=list(row['train_folds']);values[-1]^=1;row['train_folds']=values
    else:row['main'][0]['direction']['ready']=0
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=1000),row)
    with pytest.raises(AssertionError):checks.raise_failure()
    assert checks.pipeline.model.sources.tage.state()==before


@pytest.mark.parametrize('fault',('missing-old-reader','missing-final-reader','wrong-service-tag','extra-service'))
def test_final_counts_alone_cannot_close_missing_identity_or_consumer(fault):
    checks,_,_=(released if fault=='wrong-service-tag' else completed)(PROGRAMS[3])
    if fault=='missing-old-reader':checks.old_sources.pop(next(iter(checks.old_sources)))
    elif fault=='missing-final-reader':checks.new_sources.pop(next(iter(checks.new_sources)))
    else:
        value=deepcopy(checks.expected_plan[0][0])
        if fault=='wrong-service-tag':value['tag']^=1
        with pytest.raises(AssertionError):checks.write_accepted(0,transfer(1700,value))
    with pytest.raises(AssertionError):checks.finish()
    assert checks.coverage.groups['checked'].coverage==0


def test_physical_rank_label_cannot_create_a_new_functional_program():
    with pytest.raises(ValueError):RetouchReplacementCoverage(replace(PROGRAMS[0],name='physical-rank-3'))
