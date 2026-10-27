"""Definition and closure controls, never evidence that the DUT passed."""
from collections import Counter
from copy import deepcopy
from itertools import product
import pytest
from bpuverify.mbtb.model.two_key_programs import programs,SEMANTIC_PROGRAMS,RULES
from bpuverify.mbtb.coverage.two_key_lifetime import Coverage
from bpuverify.mbtb.model.entry import CARRY_PATTERNS


def receipt():
    activity=dict(requests=({'set_idx':1,'tag':2},{'set_idx':3,'tag':4}),writebacks=({'target':1},{'target':2}))
    return dict(expected_activity=deepcopy(activity),actual_activity=deepcopy(activity),
        original_metadata_unchanged=True,independent_reference_checks=10,independent_reference_failures=0)


def ready(p):
    c=Coverage(p)
    for phase in ('prepared','updated','revisited'):c.sample(dict(p.sample(),phase=phase))
    return c


def test_semantic_projection_is_complete_and_old_physical_program_set_is_retained():
    production,physical=programs('production'),programs('physical')
    assert len(production)==12 and len(physical)==192
    assert len({p.label for p in production})==12
    assert Counter(p.label for p in physical)=={p.label:16 for p in production}
    assert {tuple(p.sample()[k] for k in ('context','align','bank','way','mode','order','pair')) for p in physical}==set(
        (*c,m,o,p) for c in product(range(2),repeat=4) for m in ('blocked','flow')
        for o in ('first_second','second_first') for p in CARRY_PATTERNS)
    with pytest.raises(ValueError):programs('typo')


@pytest.mark.parametrize('p',SEMANTIC_PROGRAMS,ids=lambda p:p.label)
def test_complete_semantic_program_can_credit_only_its_own_six_obligations(p):
    c=ready(p);result=c.finish(receipt())
    assert c.groups['checked'].coverage==100/12 and set(result['completed_obligations'])==set(RULES)
    assert c.legacy.cross_coverage('all_dimensions')==100/192
    with pytest.raises(AssertionError):c.finish(receipt())


@pytest.mark.parametrize('fault',('metadata','reference-missing','reference-failed','missing-request','duplicate-identity','wrong-service'))
def test_full_phase_names_do_not_hide_a_failed_input_reference_or_service(fault):
    c=ready(SEMANTIC_PROGRAMS[0]);r=receipt()
    if fault=='metadata':r['original_metadata_unchanged']=False
    elif fault=='reference-missing':r['independent_reference_checks']=0
    elif fault=='reference-failed':r['independent_reference_failures']=1
    elif fault=='missing-request':r['actual_activity']['requests']=r['actual_activity']['requests'][:1]
    elif fault=='duplicate-identity':r['actual_activity']['requests']=(r['actual_activity']['requests'][0],)*2
    else:r['actual_activity']['writebacks']=({'target':1},{'target':999})
    with pytest.raises(AssertionError):c.finish(r)
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('count',(0,1,2))
def test_missing_consumer_phase_never_grants_partial_checked(count):
    p=SEMANTIC_PROGRAMS[0];c=Coverage(p)
    for phase in ('prepared','updated','revisited')[:count]:c.sample(dict(p.sample(),phase=phase))
    with pytest.raises(AssertionError):c.finish(receipt())
    assert c.groups['checked'].coverage==0
