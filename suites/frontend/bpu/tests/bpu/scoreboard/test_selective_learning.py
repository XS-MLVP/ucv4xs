"""Normal semantic preparation; no RTL or state-seeded golden."""
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import pytest
from bpuverify.bpu.model.pipeline import Outcome, Resolution, Redirect
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.tage.forwarding import PC
from bpuverify.bpu.model.tage.service import STREAM_PC, STREAM_POSITION, learning_inflight, pending_plan
from bpuverify.bpu.model.tage.selective_learning import PROGRAMS, LATER_PROGRAMS, ALL_PROGRAMS, DIRECTIONS, Program, preparation, eligible_counter
from bpuverify.bpu.coverage.selective_learning import Coverage, RULES
from tests.bpu.scoreboard.test_direction_forwarding import establish, resolution, values
from tests.bpu.scoreboard.test_direction_service import additional_history, via, streaming_query
from tests.bpu.scoreboard.test_direction_sources import quiet, revisit


def query(model, event, anchor, path):
    return revisit(model, event, anchor, PC) if path is None else via(model, event, anchor, path)


@lru_cache(maxsize=4)
def foundation(capacity, direction=DIRECTIONS[0]):
    program = next(p for p in ALL_PROGRAMS if p.capacity == capacity and p.direction == direction)
    model, event, anchor = establish()
    for path in program.paths[1:]: event = additional_history(model, event, anchor, path)
    for path in program.paths:
        for enabled, outcome, expected in preparation(direction):
            if event.enabled[3] != enabled:
                idle = quiet(model, event)
                event = replace(event, enabled=tuple(enabled if i == 3 else v for i, v in enumerate(event.enabled)))
                for _ in range(3): model.advance(replace(idle, enabled=event.enabled))
            original = query(model, event, anchor, path)
            idle = quiet(model, event)
            model.advance(replace(idle, feedback=resolution(original, outcome)))
            assert values(model, query(model, event, anchor, path)) == expected
        idle = quiet(model, event)
        event = replace(event, enabled=tuple(True if i == 3 else v for i, v in enumerate(event.enabled)))
        for _ in range(3): model.advance(replace(idle, enabled=event.enabled))
        assert values(model, query(model, event, anchor, path)) == ((0, 3), program.initial)
    sources = tuple(query(model, event, anchor, program.paths[h]) for h in program.feedback_order)
    loop = revisit(model, event, anchor, STREAM_PC)
    idle = quiet(model, event)
    model.advance(replace(idle, feedback=Resolution(loop.history, loop.pc,
        (Outcome(STREAM_POSITION, STREAM_PC, Kind.DIRECT, True, mispredict=True),), origin=loop)))
    quiet(model, event)
    return model, event, anchor, sources


def start(model, event, anchor):
    model.advance(replace(event, redirect=Redirect(anchor.history, anchor.pc+4, STREAM_PC, True)))
    for _ in range(8): model.advance(event)


def qualified_lifecycle(program):
    model, event, anchor, originals = deepcopy(foundation(program.capacity, program.direction))
    definitions = tuple(deepcopy(model.sources.defined_metadata(s)) for s in originals)
    start(model, event, anchor)
    commits = model.sources.tage.commits
    offered = []
    counts = [0]*len(program.paths)
    def advance(feedback=None):
        model.advance(replace(event, feedback=feedback))
        requests = model.sources.tage.offers.get((3, PC % 4), ())
        if requests: offered.append(tuple((r.way, r.entry.counter) for r in requests))
    batches = (program.first_batch,) + (() if program.boundary == 'still-pending' else ((len(originals)-1,),))
    for wave, batch in enumerate(batches):
        if wave: start(model, event, anchor)
        for index in batch:
            request = resolution(originals[index], program.outcome)
            assert not model.sources.feedback_for(request).reread
            advance(request)
            counts[program.feedback_order[index]] += 1
        for _ in range(32):
            advance()
            if not learning_inflight(model.sources.tage): break
        else: raise AssertionError('qualified old learning failed to mature')
        plan = pending_plan(model.sources.tage, 3, PC % 4)
        wanted = len(program.paths) if wave == 0 else 1
        assert tuple(map(len, plan)) == tuple(wanted if owner == program.active else 0 for owner in range(2))
        assert sorted(p['counter'] for p in plan[program.active]) == (sorted(program.counters(h, counts[h])[program.active]
            for h in range(len(program.paths))) if wave == 0 else [program.bound])
        assert model.sources.tage.commits == commits
        quiet(model, event)
        commits += sum(map(len, plan))
        assert model.sources.tage.commits == commits
        for h, path in enumerate(program.paths):
            assert values(model, query(model, event, anchor, path)) == ((0, 3), program.counters(h, counts[h]))
    assert offered == [((program.active, program.proposal),)]*len(originals)
    assert definitions == tuple(model.sources.defined_metadata(s) for s in originals)
    assert model.sources.tage.cache[3, PC % 4].overflows == 0
    selected = query(model, event, anchor, program.paths[program.target])
    idle = quiet(model, event)
    model.advance(replace(idle, feedback=resolution(selected, program.reverse_outcome)))
    changed = query(model, event, anchor, program.paths[program.target])
    assert values(model, changed) == program.reversed_values
    idle = quiet(model, event)
    model.advance(replace(idle, feedback=resolution(changed, program.restore_outcome)))
    for h, path in enumerate(program.paths):
        assert values(model, query(model, event, anchor, path)) == ((0, 3), program.counters(h, counts[h]))


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_qualified_old_first_branch_holds_independently_of_inactive_companion(program):
    qualified_lifecycle(program)


@pytest.mark.parametrize('program', LATER_PROGRAMS, ids=lambda p: p.name)
def test_complete_NT_prefix_preserves_later_old_source_upper_hold_and_reversal(program):
    qualified_lifecycle(program)


@pytest.mark.parametrize('current', range(8))
def test_per_branch_eligibility_distinguishes_original_hint_and_current_effect(current):
    assert eligible_counter(2, current, False) == (True, 1, max(0, current-1))
    assert eligible_counter(7, 7, True) == (False, 7, 7)
    assert eligible_counter(7, current, True) == (current != 7, 7, min(7, current+1))
    assert eligible_counter(5, current, True) == (True, 6, min(7, current+1))
    assert eligible_counter(0, 0, False) == (False, 0, 0)


@pytest.mark.parametrize('rule', RULES)
def test_no_checked_credit_for_an_incomplete_semantic_cohort(rule):
    coverage = Coverage(PROGRAMS[0])
    for other in RULES:
        if other != rule: coverage.compare(other, 10)
    with pytest.raises(AssertionError): coverage.finish(12)
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fields', [('invalid', 'room-remains', 'still-pending'),
    ('feedback-absent', 'bank0', 'still-pending'), ('feedback-absent', 'room-remains', 'fixed-wait'),
    ('feedback-absent', 'room-remains', 'still-pending', 'signal-port1')])
def test_program_requires_semantic_axes_not_physical_coordinates(fields):
    with pytest.raises(ValueError): Program(*fields)
