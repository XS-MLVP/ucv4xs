"""Adversarial payloads must fail without teaching the model or crediting DUTs."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.coverage.direction_turnaround import DirectionTurnaroundCoverage
from suites.frontend.bpu.bpu.model.tage.direction_turnaround import PROGRAMS
from tests.bpu.scoreboard.direction_turnaround_fixtures import armed,mixed,relearned,released,completed,packet
from tests.bpu.scoreboard.test_partial_reuse import transfer
from tests.bpu.scoreboard.test_direction_forwarding import resolution


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_fifteen_obligations_require_all_sources_actual_services_and_twelve_consumers(program):
    checks,_,retired=completed(program)
    assert checks.coverage.groups['checked'].coverage==0 and not retired
    checks.finish()
    assert all(g.coverage==100 for g in checks.coverage.groups.values())
    assert len(retired)==len(set(retired))
    with pytest.raises(AssertionError,match='single-use'):checks.finish()


@pytest.mark.parametrize('index',(1,3,5))
def test_missing_source_saturated_proposal_is_a_failure_even_when_last_input_was_accepted(index):
    checks,_,_=relearned(PROGRAMS[index],missing_last=True)
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    with pytest.raises(AssertionError,match='all complete actual proposals') as first:checks.pending()
    with pytest.raises(AssertionError) as second:checks.finish()
    assert first.value is second.value and checks.pipeline.model.sources.tage.state()==before
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('index,fault',((0,'current-result-used-as-proposal'),(0,'wrong-owner'),(0,'wrong-rank'),
    (2,'lost-neighbor'),(4,'reversed-directions'),(5,'missing-initial-proposal'),(3,'reread')))
def test_wrong_actual_learning_or_lifetimes_latch_first_exception(index,fault):
    checks,_,_=mixed(PROGRAMS[index]);checks.arm_mixed()
    checks.input_ticks.append(100400)
    row=packet(checks,index=3,plan=checks.program.pending_before(0))
    port=next(p for p in row['state']['incoming'] if p['valid'])
    if fault=='current-result-used-as-proposal':port['bits']['counter']=1
    elif fault=='wrong-owner':row['owner_hits'][0].update(owner0=(1,0,0),owner1=0)
    elif fault=='wrong-rank':row['hit_ranks']=((1,1),(1,1))
    elif fault=='lost-neighbor':row['state']['dirty']=((0,1,0,0),(0,0,0,0))
    elif fault=='reversed-directions':port['bits']['counter']=1
    elif fault=='missing-initial-proposal':port['valid']=0
    else:row['state']['reads'][1]['valid']=1
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=100408),row)
    if fault=='missing-initial-proposal':
        # Missing valid is absence, not an immediately observed bad value.
        assert not checks.offered[3:]
    else:
        with pytest.raises(AssertionError) as first:checks.raise_failure()
        with pytest.raises(AssertionError) as second:checks.finish()
        assert first.value is second.value
    assert checks.pipeline.model.sources.tage.state()==before and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('stale-counter','wrong-tag','extra-service','before-release'))
def test_actual_sdk_service_cannot_be_replaced_by_original_payload_or_extra_write(fault):
    checks,_,_=released(PROGRAMS[0])
    value=deepcopy(checks.expected_plan[0][0]);tick=100610
    if fault=='stale-counter':value['counter']^=1
    elif fault=='wrong-tag':value['tag']^=1
    elif fault=='before-release':tick=checks.release_tick
    elif fault=='extra-service':checks.write_accepted(0,transfer(tick,deepcopy(value)))
    with pytest.raises(AssertionError):checks.write_accepted(0,transfer(tick,value))
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('phase,name',(('initial','original'),('mixed','neighbor'),('blocked','original'),('serviced','displaced')))
def test_missing_real_visibility_boundary_cannot_be_closed_by_final_counts(phase,name):
    checks,_,_=completed(PROGRAMS[4]);del checks.consumers[phase,name]
    with pytest.raises(AssertionError,match='twelve'):checks.finish()
    assert checks.coverage.groups['checked'].coverage==0


def test_program_must_remain_a_reviewed_semantic_scenario_not_a_physical_slot_label():
    with pytest.raises(ValueError,match='unknown'):
        DirectionTurnaroundCoverage(replace(PROGRAMS[0],name='physical-rank-3'))


def test_a_new_misprediction_cannot_be_forged_as_correct_to_avoid_the_reread_contract():
    checks,reference,_=mixed(PROGRAMS[0]);checks.arm_mixed()
    wrong=checks.prepared_sources['negative-bound']
    checks.requests=(*checks.requests[:3],wrong)
    tick=100400;checks.input_ticks.append(tick)
    checks.pipeline.last_resolution_controls=tick,reference[1].enabled
    event=(tick,resolution(wrong.token,PROGRAMS[0].late_outcomes[0]))
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    with pytest.raises(AssertionError,match='mislabeled new misprediction'):checks.accepted_burst((event,))
    assert checks.pipeline.model.sources.tage.state()==before and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('duplicate-epoch','wrong-counter-epoch','unknown-physical-role','mutated-public-snapshot'))
def test_old_source_qualification_and_immutable_metadata_cannot_be_borrowed(fault):
    checks,_,_=mixed(PROGRAMS[0])
    before=deepcopy(checks.pipeline.model.sources.tage.state())
    with pytest.raises(AssertionError):
        if fault=='duplicate-epoch':checks.retain_prepared('positive-interior',checks.prepared_sources['positive-interior'])
        elif fault=='wrong-counter-epoch':
            del checks.prepared_sources['positive-interior']
            checks.retain_prepared('positive-interior',checks.prepared_sources['negative-interior'])
        elif fault=='unknown-physical-role':checks.retain_prepared('physical-rank-2',checks.prepared_sources['positive-interior'])
        else:
            checks.prepared_sources['positive-interior'].meta.resolve['sequence']^=1
            checks.arm_mixed()
    assert checks.pipeline.model.sources.tage.state()==before and checks.coverage.groups['checked'].coverage==0
