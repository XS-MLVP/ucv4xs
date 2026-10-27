"""Semantic feasibility from independent normal owned events, without DUTs."""
from copy import deepcopy
from dataclasses import replace

import pytest

from bpuverify.bpu.model.tage.confidence_boundary import PROGRAMS,source_counts
from bpuverify.bpu.model.tage.service import learning_inflight,pending_plan
from tests.bpu.scoreboard.confidence_boundary_fixtures import mixed
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_mixed_visibility_model import mature
from tests.bpu.scoreboard.test_asymmetric_retirement_model import concrete_plan


@pytest.mark.parametrize('initial_pc',(None,0x40000840),ids=('normal-boot','other-owned-boot'))
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_each_correct_old_source_changes_current_version_through_hold_and_reversal(program,initial_pc):
    checks,(model,event,_),_=mixed(program,initial_pc=initial_pc);checks.arm_mixed()
    tokens=tuple(s.token for s in checks.requests)
    assert len({id(t.history) for t in tokens})==len(tokens)
    frozen=tuple(deepcopy(model.sources.defined_metadata(t)) for t in tokens)
    commits=model.sources.tage.commits
    for i,(s,outcome) in enumerate(zip(checks.requests[3:],program.late_outcomes,strict=True)):
        request=resolution(s.token,outcome)
        assert not model.sources.feedback_for(request).reread
        model.advance(replace(event,feedback=request));mature(model,event)
        assert not learning_inflight(model.sources.tage)
        assert pending_plan(model.sources.tage,3,0)==concrete_plan(checks,model,tokens,program.pending_after[i])
        assert model.sources.tage.commits==commits
    assert tuple(model.sources.defined_metadata(t) for t in tokens)==frozen
    assert all(queue.drops==0 for queue in model.sources.main.directions.values())


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
def test_full_trajectory_has_unique_prepared_owners_and_a_real_boundary_hold(program):
    assert len(set(program.late_sources))==len(program.late_sources)
    assert len(program.late_sources)==len(program.pending_after)==len(program.late_outcomes)==len(program.late_proposals)
    counts=source_counts(program)
    assert all(int(name.split('#')[1])<counts[name.split('#')[0]] for name in program.late_sources)
    assert any(a==b for a,b in zip(program.pending_after,program.pending_after[1:]))
    assert all(0<=value<=7 for plan in program.pending_after for owner in plan for _,value in owner)


@pytest.mark.parametrize('name',('physical-slot-3','unreviewed-extra-feedback'))
def test_physical_or_unreviewed_trace_cannot_create_a_new_program(name):
    with pytest.raises(ValueError,match='unknown'):
        source_counts(replace(PROGRAMS[0],name=name))
