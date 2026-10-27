"""An independent logical-group oracle exposes the old insertion-only assumption."""
from dataclasses import replace

import pytest

from bpuverify.bpu.model.tage.retouch_replacement import PROGRAMS,LearningRecency
from bpuverify.tage.model.semantic import RecentLearning,TageReference,Write,Entry


@pytest.mark.parametrize('policy',('learning','insertion'))
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_core_policy_matches_independent_logical_access_oracle(program,policy):
    cache=RecentLearning(retention_policy=policy)
    snapshots=program.trace(policy=policy)
    for history,expected in zip(program.feedback_order,snapshots,strict=True):
        initial=program.initial_counters(history)
        writes=tuple(Write(history+20,way,Entry(True,100+2*history+way,
            max(0,initial[way]-1) if way==0 else min(7,initial[way]+1)),way==1) for way in range(2))
        assert cache.advance(True,writes)==()
        for way in range(2):
            actual=tuple((r.write.row-20,r.write.entry.counter) for r in sorted(
                (r for r in cache.records.values() if r.write.way==way),key=lambda r:r.rank))
            wanted=tuple((r.history,r.counters[way]) for r in expected if r is not None)
            assert actual==wanted
    assert cache.overflows==2


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_declared_victims_and_all_survivor_counters_are_pre_drive_requirements(program):
    final=program.trace()[-1]
    assert {r.history for r in final}==set(range(5))-{program.victim}
    assert next(r.counters for r in final if r.history==4)==(1,6)
    assert all(program.expected_counters(r.history)==r.counters for r in final)
    assert program.expected_counters(program.victim)==program.initial_counters(program.victim)
    legacy=program.trace(policy='insertion')[-1]
    assert (final!=legacy)==(program.victim!=0)


@pytest.mark.parametrize('bad',('actual-victim','automatic','plru-register'))
def test_policy_must_not_be_selected_from_observed_hardware(bad):
    with pytest.raises(ValueError):LearningRecency(policy=bad)
    with pytest.raises(ValueError):TageReference(retention_policy=bad)


@pytest.mark.parametrize('policy',('learning','insertion'))
def test_declared_contract_survives_reset_and_default_refreshes_hits(policy):
    declared=TageReference(retention_policy=policy);declared.reset()
    assert all(cache.retention_policy==policy for cache in declared.cache.values())
    assert RecentLearning().retention_policy=='learning'
    assert all(cache.retention_policy=='learning' for cache in TageReference().cache.values())
