"""Closed-form feasibility and fault discrimination, not DUT credit."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import ast

import pytest
from toffee import Scoreboard
from bpuverify.sc.model.semantic import Context, Events, ScReference
from bpuverify.sc.model.threshold import ScThresholdModel
from bpuverify.sc.checker.boundary import ScBoundaryChecks
from bpuverify.sc.transaction.types import ScLookup

from bpuverify.sc.model import neutral_boundary as programs

MODULE = Path(programs.__file__)
Program, PROFILES = programs.NeutralBoundaryProgram, programs.PROFILES


def lookup(model, program, pc=None):
    model.advance(Events(pc=program.pc if pc is None else pc))
    model.advance(Events(advance=True))
    model.advance(Events(select=True, branches=program.layout))
    return model.prediction


def settle(model):
    # Deadline derives from two learning stages and retained-write capacity;
    # completion is the actual pure model's empty obligation state.
    capacity = max(len(cache.rows) for family in model.writes for cache in family)
    for _ in range(2 + capacity):
        model.advance()
        if model.learning is None and not model.pending and all(
                row is None or not row.dirty for family in model.writes for cache in family for row in cache.rows):
            return
    raise AssertionError('pure learning obligations did not retire')


def compare(model, program, prediction, weight, thresholds):
    expected = program.expected(weight, thresholds)
    actual = dict(takens=prediction.directions, useds=prediction.used,
        meta=prediction.metadata(),
        families={name: tuple(component[index] for component in prediction.components)
                  for index, name in enumerate(programs.FAMILY_FIELDS)})
    Scoreboard('sc.neutral-boundary-feasibility').check(expected=expected, actual=actual)
    assert prediction.sums == program.scores(weight)
    assert model.thresholds.values == thresholds
    # Pure model inspection checks hand-computed family magnitudes too; the
    # later DUT program must use observable exact-recovery consumers instead.
    columns = (1,)*7 + (7 if program.direction else 6,)
    assert tuple(row[column] for row, column in zip(prediction.read.weights, columns, strict=True)) == (weight,) * 8


def test_closed_form_has_only_semantic_transaction_dependencies():
    tree = ast.parse(MODULE.read_text())
    assert [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] == [
        'bpuverify.common.model.configuration', 'dataclasses', 'bpuverify.sc.transaction.types']
    assert not any(isinstance(n, ast.Import) for n in ast.walk(tree))


@pytest.mark.parametrize('boundary,placement', PROFILES)
def test_distinct_cold_sources_neutral_boundary_and_exact_fresh_recovery(boundary, placement):
    program, model = Program(boundary, placement), ScReference()
    thresholds = ScThresholdModel()
    cold = tuple(lookup(model, program) for _ in range(program.cold_source_count))
    frozen = tuple(deepcopy(p.metadata()) for p in cold)
    assert len({id(p) for p in cold}) == program.cold_source_count
    assert all(p.sums == (8,) * 10 and p.used == (0,) * 10 for p in cold)
    for step, source in enumerate(cold[:-1], 1):
        feedback = program.seed(source.metadata())
        assert thresholds.apply(feedback).qualifying_slots == (program.prefix_slots[0],)
        model.advance(Events(feedback=feedback))
        settle(model)
        compare(model, program, lookup(model, program), program.weight(step), program.thresholds(step))
    request = program.neutral(cold[-1].metadata())
    assert tuple((b.position, b.actual_taken) for b in request.branches) == ((1, 0), (8, 1))
    update = thresholds.apply(request)
    assert update.qualifying_slots == program.prefix_slots
    assert update.before == update.after == program.thresholds(program.seed_count)
    model.advance(Events(feedback=request))
    settle(model)
    current = lookup(model, program)
    compare(model, program, current, program.endpoint, program.thresholds(program.seed_count))
    assert lookup(model, program, pc=program.pc + 16).read.weights == ((0,) * 8,) * 7 + ((0,) * 32,)
    for step in range(1, program.reverse_steps + 1):
        request = program.reverse(current.metadata())
        assert thresholds.apply(request).qualifying_slots == (program.prefix_slots[0],)
        model.advance(Events(feedback=request))
        settle(model)
        current = lookup(model, program)
        compare(model, program, current, program.weight(program.seed_count, step),
                program.thresholds(program.seed_count, step))
        assert current.directions[:2] == ((program.direction,) * 2 if step < 32 else (1 - program.direction,) * 2)
    assert frozen == tuple(p.metadata() for p in cold)
    assert model.snapshot(program.pc + 16, Context()).weights == ((0,) * 8,) * 7 + ((0,) * 32,)


@pytest.mark.parametrize('fault', ('drop-first', 'drop-second', 'sequential-clamp', 'sequential-resolved-clamp'))
def test_the_four_legal_programs_collectively_distinguish_vote_order_or_missing_votes(fault):
    detected = []
    for boundary, placement in PROFILES:
        program = Program(boundary, placement)
        feedback = program.neutral(program.expected(0, (1130,) * 8)['meta'])
        ordered = list(feedback.branches) if fault == 'sequential-resolved-clamp' else sorted(feedback.branches, key=lambda b: b.prediction_slot)
        if fault == 'drop-first':
            ordered = ordered[1:]
        elif fault == 'drop-second':
            ordered = ordered[:1]
        wrong = program.endpoint
        for branch in ordered:
            wrong = max(-32, min(31, wrong + (1 if branch.actual_taken else -1)))
        if wrong != program.endpoint:
            # At the last pre-crossing consumer, a one-unit bias changes the
            # five public family signs even if a prior output sign was stable.
            inward = -1 if program.direction else 1
            expected = program.expected(program.endpoint + inward * 31, program.thresholds(program.seed_count, 31))
            actual = program.expected(wrong + inward * 31, program.thresholds(program.seed_count, 31))
            with pytest.raises(AssertionError):
                Scoreboard('sc.neutral-boundary-negative').check(expected=expected, actual=actual)
            detected.append(program.label)
    assert len(detected) == 2


@pytest.mark.parametrize('boundary,placement', PROFILES)
def test_current_confidence_cannot_replace_the_original_dual_source_qualification(boundary, placement):
    program = Program(boundary, placement)
    cold = program.expected(0, (1130,) * 8)['meta']
    hot = program.expected(program.endpoint, program.thresholds(program.seed_count))['meta']
    original = ScThresholdModel().apply(program.neutral(cold))
    replaced = ScThresholdModel().apply(program.neutral(hot))
    assert original.qualifying_slots == program.prefix_slots
    assert len(replaced.qualifying_slots) == 1
    assert replaced.after != replaced.before


@pytest.mark.parametrize('boundary,placement', PROFILES)
@pytest.mark.parametrize('family', programs.FAMILY_FIELDS)
def test_one_family_bias_is_detected_even_when_overall_prediction_and_confidence_are_identical(boundary, placement, family):
    program = Program(boundary, placement)
    expected = program.expected(program.weight(program.seed_count, 31), program.thresholds(program.seed_count, 31))
    actual = deepcopy(expected)
    # A one-unit inward bias flips this family's two shared signs one
    # response too early; the five-family total remains on the same side.
    actual['families'][family] = (1 - expected['families'][family][0],
                                 1 - expected['families'][family][1], 1, 1)
    assert actual['takens'] == expected['takens'] and actual['meta'] == expected['meta']
    with pytest.raises(AssertionError):
        Scoreboard('sc.neutral-boundary-family-negative').check(expected=expected, actual=actual)


@pytest.mark.parametrize('boundary,placement', PROFILES)
def test_final_consumer_rejects_one_missing_fresh_reverse_feedback(boundary, placement):
    program = Program(boundary, placement)
    thresholds = program.thresholds(program.seed_count, 32)
    expected = program.expected(program.weight(program.seed_count, 32), thresholds)
    actual = program.expected(program.weight(program.seed_count, 31), thresholds)
    with pytest.raises(AssertionError):
        Scoreboard('sc.neutral-boundary-missing-recovery').check(expected=expected, actual=actual)


@pytest.mark.parametrize('boundary,placement', PROFILES)
def test_existing_source_ledger_rejects_modified_original_metadata_before_feedback(boundary, placement):
    program = Program(boundary, placement)
    expected = program.expected(0, (1130,) * 8)
    actual = SimpleNamespace(takens=expected['takens'], useds=expected['useds'],
        meta=dict(deepcopy(expected['meta']), debug=deepcopy(expected['families'])))
    transfer = SimpleNamespace(sequence_id=1,
        request=ScLookup(program.pc, 0, 0, branches=program.layout),
        accepted_event=SimpleNamespace(tick=10), completed_event=SimpleNamespace(tick=12))
    checks = ScBoundaryChecks(program)
    source = checks.source(transfer, actual, expected, state='pure source-ledger negative control')
    actual.meta['scPred'] = (0, 1, 1, 1)
    with pytest.raises(AssertionError):
        checks.feedback(source)
    assert not checks.spent
