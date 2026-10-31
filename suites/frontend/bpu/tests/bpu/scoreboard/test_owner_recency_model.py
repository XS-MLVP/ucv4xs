"""Independent-owner access histories must not become a global paired age."""
from copy import deepcopy

import pytest

from suites.frontend.bpu.bpu.model.tage.owner_recency import PROGRAMS,OwnerRecency
from suites.frontend.bpu.tage.model.semantic import RecentLearning,Write,Entry


@pytest.mark.parametrize('policy',('learning','insertion'))
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_core_cache_and_two_independent_recent_history_models_agree(program,policy):
    cache=RecentLearning(retention_policy=policy)
    for i,(history,expected) in enumerate(zip(program.feedback_order,program.trace(policy=policy),strict=True)):
        initial=program.initial_counters(history)
        writes=tuple(Write(history+20,o,Entry(True,100+2*history+o,
            max(0,initial[o]-1) if o==0 else min(7,initial[o]+1)),bool(o)) for o in program.input_owners(i))
        assert cache.advance(True,writes)==()
        for o in range(2):
            actual=tuple((v.write.row-20,v.write.entry.counter) for v in sorted(
                (v for v in cache.records.values() if v.write.way==o),key=lambda v:v.rank))
            assert actual==tuple((r.history,r.counter) for r in expected[o] if r is not None)
    assert cache.overflows==2


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_unprovided_branch_and_its_recency_are_unchanged_before_next_new_identity(program):
    model=OwnerRecency()
    for i,h in enumerate(program.feedback_order):
        before=deepcopy(model.__dict__)
        owners=program.input_owners(i)
        model.learn(h,owners,program.initial_counters(h))
        for o in set(range(2))-set(owners):
            assert model.residents[o]==before['residents'][o]
            assert model.latest_group[o]==before['latest_group'][o]
            assert model.latest_member[o]==before['latest_member'][o]
            assert model.removed[o]==before['removed'][o]
    assert tuple(v[0] for v in model.removed)==program.victims


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_declared_owner_victims_and_mixed_final_visibility_are_not_sampled(program):
    final=program.trace()[-1]
    for o in range(2):
        assert {r.history for r in final[o]}==set(range(5))-{program.victims[o]}
        for h in range(5):
            wanted=next((r.counter for r in final[o] if r.history==h),program.initial_counters(h)[o])
            assert program.expected_counters(h)[o]==wanted
    assert program.main_update_counts==tuple(5+sum(o==p for h,p in program.retouches) for o in range(2))
    assert (program.trace(policy='insertion')[-1]!=final)==(program.victims!=(0,0))


def test_disjoint_owner_accesses_commute_but_do_not_share_a_victim():
    a,b=PROGRAMS[-2:]
    assert a.trace()[-1]==b.trace()[-1]
    assert a.victims==b.victims==(2,0)
    assert a.expected_counters(0)==(0,6)
    assert a.expected_counters(2)==(2,7)


@pytest.mark.parametrize('subset',((),(2,),(1,0),(0,0),(False,)))
def test_unknown_or_duplicate_feedback_subset_is_not_an_implicit_pair(subset):
    # bool is not a branch identity, despite Python's numeric equality.
    with pytest.raises(ValueError):OwnerRecency().learn(0,subset,(1,6))
