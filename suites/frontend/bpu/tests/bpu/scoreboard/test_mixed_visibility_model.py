"""Owned normal events prove feasibility; no DUT state seeds or coverage credit."""
from copy import deepcopy
from dataclasses import replace

import pytest

from bpuverify.bpu.model.pipeline import Redirect
from bpuverify.bpu.model.tage.asymmetric_retirement import OUTCOMES, PRELUDE_PLAN
from bpuverify.bpu.model.tage.mixed_visibility import PROGRAMS, PARTIAL_PLAN
from bpuverify.bpu.model.tage.neighbor_migration import PC, HISTORY_PATHS
from bpuverify.bpu.model.tage.service import STREAM_PC, learning_inflight, pending_plan
from tests.bpu.scoreboard.test_asymmetric_retirement_model import prepare_model, concrete_plan
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_direction_service import via, streaming_query
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_dual_migration import source


def consumers(checks, model, event, anchor, program, phase):
    result = {}
    for name, path in HISTORY_PATHS.items():
        middle = streaming_query(model, event, anchor.history, path, anchor.pc + 4)
        token = streaming_query(model, event, middle.history, PC, path + 4)
        assert checks.profile(source(model, token, 60000)) == program.profile(phase, name)
        result[name] = token
    return result


def mature(model, event):
    for _ in range(16):
        model.advance(event)
        if not learning_inflight(model.sources.tage):
            return
    raise AssertionError('independent mixed-visibility effects did not mature')


@pytest.mark.parametrize('initial_pc', (None, PC + 0x40), ids=('normal-boot', 'different-owned-boot'))
@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_normal_partial_service_and_real_mixed_sources_keep_all_independent_results(program, initial_pc):
    checks, model, event, anchor, inputs = prepare_model(initial_pc=initial_pc)
    old_neighbor = via(model, event, anchor, HISTORY_PATHS['neighbor'])
    frozen = {id(t): deepcopy(model.sources.defined_metadata(t)) for t in (*inputs, old_neighbor)}
    model.advance(replace(quiet(model, event), redirect=Redirect(anchor.history, anchor.pc + 4, STREAM_PC, True)))
    for _ in range(8):
        model.advance(event)
    before = model.sources.tage.commits
    for token, outcomes in zip(inputs[:3], OUTCOMES[:3], strict=True):
        model.advance(replace(event, feedback=resolution(token, outcomes)))
    mature(model, event)
    assert pending_plan(model.sources.tage, 3, PC % 4) == concrete_plan(checks, model, inputs, PRELUDE_PLAN)
    consumers(checks, model, event, anchor, program, 'initial')
    model.advance(replace(event, prediction_ready=False))
    assert model.sources.tage.commits == before + 2
    for _ in range(8):
        model.advance(event)
    assert pending_plan(model.sources.tage, 3, PC % 4) == concrete_plan(checks, model, inputs, PARTIAL_PLAN)
    mixed = consumers(checks, model, event, anchor, program, 'mixed')
    saved = {'old-target': inputs[3], 'old-neighbor': old_neighbor,
             'mixed-target': mixed['original'], 'mixed-neighbor': mixed['neighbor']}
    late = tuple(saved[n] for n in program.late_sources)
    used = (*inputs[:3], *late)
    assert len({id(t.history) for t in used}) == len(used)
    for token in late:
        frozen.setdefault(id(token), deepcopy(model.sources.defined_metadata(token)))
    assert pending_plan(model.sources.tage, 3, PC % 4) == concrete_plan(checks, model, inputs, PARTIAL_PLAN)
    for token, outcomes in zip(late, program.late_outcomes, strict=True):
        request = resolution(token, outcomes)
        assert not model.sources.feedback_for(request).reread
        model.advance(replace(event, feedback=request))
    mature(model, event)
    assert model.sources.tage.commits == before + 2
    assert pending_plan(model.sources.tage, 3, PC % 4) == concrete_plan(checks, model, inputs, program.final_plan)
    consumers(checks, model, event, anchor, program, 'blocked')
    quiet(model, event)
    assert model.sources.tage.commits - before == 2 + sum(map(len, program.final_plan))
    for name, path in HISTORY_PATHS.items():
        token = via(model, event, anchor, path)
        assert checks.profile(source(model, token, 61000)) == program.profile('serviced', name)
    assert all(model.sources.defined_metadata(t) == frozen[id(t)] for t in used)


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_declared_programs_have_distinct_semantic_sources_and_different_remaining_service_shapes(program):
    assert len(program.late_sources) == len(program.late_outcomes) == len(program.late_proposals) == len(program.pending_after)
    assert len(set(program.late_sources)) == len(program.late_sources)
    expected = {'both-old-identities': (2, 2), 'old-target-only': (1, 2),
                'fresh-target-mixed': (1, 1), 'fresh-neighbor-mixed': (2, 1)}
    assert tuple(map(len, program.final_plan)) == expected[program.name]


@pytest.mark.parametrize('phase,name', (('whole-history-committed', 'original'), ('mixed', 'physical-rank-2')))
def test_unreviewed_visibility_and_physical_labels_are_not_new_functional_requirements(phase, name):
    with pytest.raises(ValueError, match='undeclared'):
        PROGRAMS[0].profile(phase, name)
