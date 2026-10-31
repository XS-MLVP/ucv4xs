"""Normal-event feasibility and closed semantic expectations; no DUT credit."""
from suites.frontend.bpu.models.configuration import TAGE_ALLOCATION_WAIT
from copy import deepcopy
from dataclasses import replace

import pytest

from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.model.pipeline import Outcome, Redirect, Resolution
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.tage.partial_residency import PC, PATHS, POSITIONS, PROGRAMS
from suites.frontend.bpu.bpu.model.tage.service import (
    STREAM_PC, STREAM_POSITION, learning_inflight, pending_plan)
from suites.frontend.bpu.tage.model.semantic import coordinate
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_direction_service import streaming_query, via
from tests.bpu.scoreboard.test_direction_sources import prepared, quiet, revisit


def profile(model, token):
    entries = tuple(e for row in source_entries(token.lookup) for e in row)
    main = tuple(next((e.counter for e in entries if e.hit and e.position == p), None) for p in POSITIONS)
    read = model.sources.snapshot(token).read
    tagged = tuple(None if read is None else next(iter(read.matches(p)), None) for p in POSITIONS)
    return main, tagged


def prepare_program(program):
    model, event, anchor = prepared()
    loop = revisit(model, event, anchor, STREAM_PC)
    model.advance(replace(quiet(model, event), feedback=Resolution(loop.history, STREAM_PC,
        (Outcome(STREAM_POSITION, STREAM_PC, Kind.DIRECT, True, mispredict=True),), origin=loop)))
    quiet(model, event)
    saved = {}
    for step in program.preparation():
        idle = quiet(model, event)
        if event.enabled[3] != step.enabled:
            event = replace(event, enabled=tuple(step.enabled if i == 3 else x
                                                for i, x in enumerate(event.enabled)))
            for _ in range(3):
                model.advance(replace(idle, enabled=event.enabled))
        token = via(model, event, anchor, PATHS[step.context])
        idle = quiet(model, event)
        request = resolution(token, step.outcomes)
        if step.allocation is not None:
            feedback = model.sources.feedback_for(request)
            for _ in range(TAGE_ALLOCATION_WAIT):
                if model.sources.tage.allocation_at_next_accept(feedback) == step.allocation:
                    break
                model.advance(idle)
            else:
                raise AssertionError(('normal allocation opportunity absent', step.name))
        model.advance(replace(idle, feedback=request))
        after = via(model, event, anchor, PATHS[step.context])
        assert profile(model, after) == step.expected, step.name
        for index, name in enumerate(program.capture_names(step)):
            actual = after if index == 0 else via(model, event, anchor, PATHS['original'])
            assert name not in saved and profile(model, actual) == program.source_profile(name)
            saved[name] = actual
    assert set(saved) == set(program.source_names)
    assert len({id(t.history) for t in saved.values()}) == len(saved)
    current = {name: via(model, event, anchor, path) for name, path in PATHS.items()}
    assert {name: profile(model, token) for name, token in current.items()} == {
        name: program.initial_profile(name) for name in PATHS}
    return model, event, anchor, saved, current


def payloads(model, sources):
    original = next(iter(sources.values()))
    read = model.sources.snapshot(original).read
    row, raw = coordinate(PC, read.context, 3)[1:]
    return {name: dict(row=row, valid=1, tag=raw ^ p)
            for name, p in zip(('a', 'b'), POSITIONS, strict=True)}


def concrete(logical, identities):
    return tuple(None if item is None else dict(identities[item[0]], counter=item[1]) for item in logical)


def execute_stage(program, ordinal, model, event, anchor, saved):
    stage = program.stages[ordinal]
    identities = payloads(model, saved)
    model.advance(replace(quiet(model, event), redirect=Redirect(anchor.history, anchor.pc + 4, STREAM_PC, True)))
    for _ in range(8):
        model.advance(event)
    cache = model.sources.tage.cache[7, PC % 4]
    before = cache.overflows
    for name, outcomes in zip(stage.sources, stage.outcomes, strict=True):
        request = resolution(saved[name], outcomes)
        assert not model.sources.feedback_for(request).reread
        model.advance(replace(event, feedback=request))
    changes = []
    previous = ((), ())
    for _ in range(16):
        model.advance(event)
        pending = pending_plan(model.sources.tage, 7, PC % 4)
        if pending != previous:
            changes.append(tuple(p[0] if p else None for p in pending))
            previous = pending
        if not learning_inflight(model.sources.tage):
            break
    assert changes == [concrete(p, identities) for p in stage.pending_after]
    assert cache.overflows - before == stage.pending_replacements
    for name, path in PATHS.items():
        mid = streaming_query(model, event, anchor.history, path, anchor.pc + 4)
        token = streaming_query(model, event, mid.history, PC, path + 4)
        assert profile(model, token) == program.profile(ordinal, name, serviced=False)
    quiet(model, event)
    for name, path in PATHS.items():
        token = via(model, event, anchor, path)
        assert profile(model, token) == program.profile(ordinal, name, serviced=True)
    assert pending_plan(model.sources.tage, 7, PC % 4) == ((), ())


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_normal_preparation_and_every_planned_residency_transition_have_closed_expected_consumers(program):
    model, event, anchor, saved, _ = prepare_program(program)
    frozen = {name: deepcopy(model.sources.defined_metadata(token)) for name, token in saved.items()}
    for ordinal in range(len(program.stages)):
        execute_stage(program, ordinal, model, event, anchor, saved)
    assert {name: model.sources.defined_metadata(token) for name, token in saved.items()} == frozen


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_no_case_reuses_a_source_or_relies_on_undefined_simultaneous_destination_arbitration(program):
    assert len(program.source_names) == len(set(program.source_names))
    assert len(tuple(program.preparation())) == (27 if program.saturated_source else 23)
    for stage in program.stages:
        assert len(stage.sources) == len(stage.outcomes) == len(stage.proposals) == len(stage.pending_after)
        assert all(sum(p is not None for p in ports) == 1 for ports in stage.proposals)
        assert sum(p is not None for p in stage.service) == 1


@pytest.mark.parametrize('name', ('unregistered', 'new-random-bank'))
def test_unreviewed_source_names_do_not_acquire_old_identity_or_counter_state(name):
    with pytest.raises(ValueError, match='undeclared'):
        PROGRAMS[0].source_profile(name)


@pytest.mark.parametrize('stage,name', ((-1, 'original'), (True, 'original'), (4, 'displaced'), (0, 'unregistered')))
def test_consumer_plan_cannot_silently_expand_its_declared_semantic_scope(stage, name):
    with pytest.raises(ValueError, match='undeclared'):
        PROGRAMS[0].profile(stage, name, serviced=True)
