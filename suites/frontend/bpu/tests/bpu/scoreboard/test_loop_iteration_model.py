"""Semantic iteration/version tests; synthetic cycles contribute no DUT coverage."""
from dataclasses import replace

import pytest

from bpuverify.bpu.model.loop_iteration import LoopIterationReference, MAX_ITERATIONS, loop_successor
from bpuverify.bpu.model.pipeline import Cycle, Token
from bpuverify.bpu.model.path_history import Checkpoint
from bpuverify.bpu.model.selection import Branch, Choice, Kind

PC = 0x40000800
BACK = Branch(1, PC, Kind.CONDITIONAL, True)


def token(sequence, pc=PC):
    return Token(sequence, pc, Checkpoint(sequence, 0, 0), None)


def stage_token(source):
    return Token(source.token_sequence, source.pc, source.owner, None)


def cycle(*, tokens=(None, None, None), branches=(None, None, None), issue=False, early=False, middle=False, final=False):
    choices = tuple(None if b is None else Choice(b, None, 'independent-unit-program') for b in branches)
    return Cycle(tokens, choices, (issue, early, tokens[1] is not None, tokens[2] is not None),
                 (False,) * 3, middle, final, None, tokens[2], PC, (False,) * 7)


def natural(count):
    model = LoopIterationReference()
    current = token(0)
    model.advance(cycle(issue=True), issued=current)
    sources = [model.snapshot(current)]
    for i in range(count):
        next_token = token(i + 1)
        model.advance(cycle(tokens=(current, None, None), branches=(BACK, None, None), issue=True, early=True), issued=next_token)
        current = next_token
        sources.append(model.snapshot(current))
    return model, current, sources


@pytest.mark.parametrize('branch,expected', (
    (BACK, 8), (replace(BACK, taken=False), 0), (replace(BACK, target=PC + 0x100), 0),
    (replace(BACK, kind=Kind.DIRECT), 0), (replace(BACK, kind=Kind.INDIRECT), 0),
    (Branch(0, PC + 16, Kind.NONE, False), 0),
    (replace(BACK, target=PC + (1 << 20)), 8),
))
def test_only_taken_backward_conditionals_extend_the_original_loop_iteration(branch, expected):
    assert loop_successor(7, PC, branch) == expected


def test_natural_iterations_reach_the_bound_and_never_wrap_while_metadata_remains_original():
    model, current, sources = natural(MAX_ITERATIONS + 2)
    assert model.cursor == MAX_ITERATIONS
    assert [s.count for s in sources[:4]] == [0, 1, 2, 3]
    assert [s.count for s in sources[-3:]] == [MAX_ITERATIONS] * 3
    before = model.state()
    model.advance(cycle())
    assert model.cursor == MAX_ITERATIONS and model.snapshot(current).count == MAX_ITERATIONS
    assert before['owned'] == model.state()['owned']


@pytest.mark.parametrize('branch,expected', ((BACK, 6), (replace(BACK, taken=False), 0),
    (replace(BACK, target=PC + 0x100), 0), (replace(BACK, kind=Kind.DIRECT), 0)))
def test_recovery_recomputes_from_old_owned_iterations_not_the_younger_saturated_cursor(branch, expected):
    model, _, sources = natural(MAX_ITERATIONS)
    original = sources[5]
    model.advance(cycle(), recovery=(original, branch))
    assert model.cursor == expected and original.count == 5


def test_saturated_original_recovery_holds_the_bound_instead_of_wrapping_to_zero():
    model, _, sources = natural(MAX_ITERATIONS)
    model.advance(cycle(), recovery=(sources[-1], BACK))
    assert model.cursor == MAX_ITERATIONS


def test_oldest_correction_wins_over_younger_predictions_and_has_its_own_source():
    model, current, sources = natural(20)
    oldest, middle, youngest = stage_token(sources[5]), stage_token(sources[10]), current
    both = cycle(tokens=(youngest, middle, oldest), branches=(BACK, BACK, BACK), early=True, middle=True, final=True)
    model.advance(both)
    assert model.cursor == sources[5].count + 1 == 6
    model, current, sources = natural(20)
    both = cycle(tokens=(current, stage_token(sources[10]), stage_token(sources[5])), branches=(BACK, BACK, BACK), early=True, middle=True, final=True)
    model.advance(both, recovery=(sources[2], BACK))
    assert model.cursor == 3


def test_middle_correction_uses_its_immutable_prediction_not_current_speculation():
    model, current, sources = natural(20)
    model.advance(cycle(tokens=(current, stage_token(sources[10]), None), branches=(BACK, BACK, None), early=True, middle=True))
    assert model.cursor == sources[10].count + 1 == 11


@pytest.mark.parametrize('fault', ('copied', 'foreign', 'retired', 'reset', 'same-encoding-new-owner'))
def test_equal_values_do_not_replace_an_owned_recovery_identity(fault):
    model, _, sources = natural(5)
    original = sources[2]
    if fault == 'copied': original = replace(original)
    elif fault == 'foreign': original = natural(5)[2][2]
    elif fault == 'retired': model.retire(original)
    elif fault == 'reset': model.reset()
    else:
        foreign = replace(token(2), history=replace(token(2).history))
        with pytest.raises(ValueError, match='own'):
            model.snapshot(foreign)
        return
    before = model.state()
    with pytest.raises(ValueError, match='owned'):
        model.preview(cycle(), recovery=(original, BACK))
    assert model.state() == before


@pytest.mark.parametrize('fault', ('copied', 'forged-count', 'stale', 'foreign', 'missing-issue'))
def test_preview_cannot_seed_a_counter_from_observed_values_or_be_applied_twice(fault):
    model, current, _ = natural(2)
    step = model.preview(cycle(tokens=(current, None, None), branches=(BACK, None, None), early=True, issue=True))
    if fault == 'copied': step = replace(step)
    elif fault == 'forged-count': step = replace(step, after=100)
    elif fault == 'stale': model.reset()
    elif fault == 'foreign':
        other, _, _ = natural(2); step = other.preview(cycle())
    before = model.state()
    with pytest.raises(ValueError):
        model.apply(step, issued=None if fault == 'missing-issue' else token(3))
    assert model.state() == before


@pytest.mark.parametrize('value', (-1, 256, True, 1.0, {'actual': 3}))
def test_invalid_or_signal_like_counts_are_rejected_instead_of_truncated(value):
    with pytest.raises(ValueError):
        loop_successor(value, PC, BACK)


def test_preview_is_nonmutating_and_only_one_exact_step_can_advance_the_reference():
    model, current, _ = natural(2)
    before = model.state()
    step = model.preview(cycle(tokens=(current, None, None), branches=(BACK, None, None), early=True, issue=True))
    assert model.state() == before and step.after == 3
    issued = token(3)
    source = model.apply(step, issued=issued)
    assert model.cursor == 3 and source is model.snapshot(issued)
    before = model.state()
    with pytest.raises(ValueError, match='already applied'):
        model.apply(step, issued=issued)
    assert model.state() == before


def test_retiring_the_source_between_preview_and_commit_invalidates_the_proposal():
    model, current, sources = natural(2)
    step = model.preview(cycle(), recovery=(sources[0], BACK))
    model.retire(sources[0]);before = model.state()
    with pytest.raises(ValueError, match='owned'):
        model.apply(step)
    assert model.state() == before and model.snapshot(current).count == 2
