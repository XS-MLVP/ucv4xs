"""Negative controls for semantic closure, not fake DUT coverage."""
from collections import Counter
from copy import deepcopy
from itertools import product
import pytest
from bpuverify.mbtb.model.cleanup_programs import SEMANTIC_PROGRAMS,RULES,programs
from bpuverify.mbtb.coverage.cleanup_lifetime import Coverage,PHASES


def ready(program):
    c=Coverage(program)
    for phase in PHASES:c.sample(dict(program.sample(),phase=phase))
    return c


def receipt():
    dual=dict(ports=[dict(write_valid=1,key='neighbor'),dict(write_valid=1,key='duplicate')],foreign_writes=[])
    return dict(expected_dual=deepcopy(dual),actual_dual=dual,
        expected_feedback={'complete':'accepted'},actual_feedback={'complete':'accepted'},
        original_metadata_unchanged=True,independent_reference_checks=12,independent_reference_failures=0,
        public_profiles_checked=True,request_offset=4,integrated_ftq_reachability_proven=False)


def test_projection_keeps_every_old_physical_program_without_promoting_it_to_another_feature():
    assert len(programs('production'))==12 and len(programs('physical'))==48
    assert Counter(p.label for p in programs('physical'))=={p.label:4 for p in SEMANTIC_PROGRAMS}
    assert {tuple(p.sample()[k] for k in ('align','bank','depth','shadow_state','key')) for p in programs('physical')}==set(
        (*coords,state,key) for coords in product(range(2),repeat=3) for state in ('dirty','clean')
        for key in ('zero_tag','zero_position','nonzero'))
    with pytest.raises(ValueError):programs('typo')


@pytest.mark.parametrize('program',SEMANTIC_PROGRAMS,ids=lambda p:p.label)
def test_checked_requires_complete_feedback_two_effects_and_consumers(program):
    c=ready(program);r=c.finish(receipt())
    assert r['completed_obligations']==list(RULES)
    assert c.groups['checked'].coverage==100/12
    assert c.legacy.cross_coverage('all_dimensions')==100/48
    with pytest.raises(AssertionError):c.finish(receipt())


@pytest.mark.parametrize('fault',('metadata','reference','missing-reference','consumer','late-effect','missing-clear','wrong-feedback','foreign-effect'))
def test_named_phases_cannot_hide_incomplete_or_wrong_effects(fault):
    c=ready(SEMANTIC_PROGRAMS[0]);r=receipt()
    if fault=='metadata':r['original_metadata_unchanged']=False
    elif fault=='reference':r['independent_reference_failures']=1
    elif fault=='missing-reference':r['independent_reference_checks']=0
    elif fault=='consumer':r['public_profiles_checked']=False
    elif fault=='late-effect':r['request_offset']=6
    elif fault=='missing-clear':r['actual_dual']['ports'].pop()
    elif fault=='wrong-feedback':r['actual_feedback']['complete']='wrong'
    else:r['actual_dual']['foreign_writes'].append((0,1,0))
    with pytest.raises(AssertionError):c.finish(r)
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('count',(0,1,2))
def test_all_consumer_phases_are_required(count):
    p=SEMANTIC_PROGRAMS[0];c=Coverage(p)
    for phase in PHASES[:count]:c.sample(dict(p.sample(),phase=phase))
    with pytest.raises(AssertionError):c.finish(receipt())
    assert c.groups['checked'].coverage==0
