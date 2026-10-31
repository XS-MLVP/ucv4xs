"""Closed-form qualification and lifetime-credit controls; no hardware credit."""
import pytest

from suites.frontend.bpu.utage.model.semantic import Context, Events, Feedback, Source, UtageReference, indices
from suites.frontend.bpu.utage.model.enable_lifetime import (
    Program, TABLES, PHASES, RULES, PC, POSITION, HISTORY, NEIGHBOR_HISTORY)
from suites.frontend.bpu.utage.coverage.enable_lifetime import Coverage


@pytest.mark.parametrize('table', TABLES)
@pytest.mark.parametrize('phase', PHASES)
def test_only_qualified_original_learning_changes_the_selected_identity(table, phase):
    program = Program(table, phase)
    expected = program.reward(program.initial) if phase == 'after-qualification' else program.initial
    assert program.disabled == expected
    assert program.reopened_learning == program.reward(expected)
    before, after = program.protection(program.initial), program.protection(program.disabled)
    selected = table * 512 + indices(PC, Context.from_recent(HISTORY))[table]
    assert [index for index, (a, b) in enumerate(zip(before, after)) if a != b] == (
        [selected] if program.qualifies else [])
    neighbor = table * 512 + indices(PC, Context.from_recent(NEIGHBOR_HISTORY))[table]
    assert neighbor != selected and before[neighbor] == after[neighbor] == program.initial.useful


@pytest.mark.parametrize('phase', PHASES)
def test_independent_reference_distinguishes_offer_qualification_and_irrevocable_learning(phase):
    model = UtageReference()
    context = Context.from_recent(HISTORY)
    feedback = Feedback(PC, context, indices(PC, context),
        (Source(True, POSITION, False, 0, 0, False, True),), POSITION, False)
    model.advance(Events(feedback=feedback))
    model.advance(Events(enabled=phase == 'after-qualification'))
    model.advance(Events(enabled=False))
    model.advance(Events(enabled=False))
    model.advance(Events(enabled=True))
    qualifies = phase == 'after-qualification'
    assert model.accepted_feedback == int(qualifies)
    assert model.useful[0].get(feedback.indices[0], 0) == int(qualifies)
    assert model.offered is None and model.learning is None
    assert len(model.updates[0].recent) == int(qualifies)


@pytest.mark.parametrize('table', TABLES)
@pytest.mark.parametrize('phase', PHASES)
@pytest.mark.parametrize('missing', RULES)
def test_partial_learning_lifetime_never_gets_checked_credit(table, phase, missing):
    coverage = Coverage(Program(table, phase))
    for rule in RULES:
        if rule != missing:
            coverage.reached(rule)
    with pytest.raises(AssertionError):
        coverage.finish()
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('table,phase', ((True, PHASES[0]), (-1, PHASES[0]),
    (2, PHASES[1]), (0, 'arbitrary-delay'), (1, 'after-reset')))
def test_unknown_or_aliased_lifetime_is_not_an_extra_functional_profile(table, phase):
    with pytest.raises(ValueError):
        Program(table, phase)
