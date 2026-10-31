"""Independent expanded-stack and evidence controls, not hardware credit."""
import pytest

from suites.frontend.bpu.ras.model.model import CommittedStack, advance
from suites.frontend.bpu.ras.model.semantic import Events, RasReference
from suites.frontend.bpu.bpu.model.ras.nested_recursion import (
    OUTER_RETURN, INNER_RETURN, PROFILES, RULES, expanded_returns)
from suites.frontend.bpu.bpu.coverage.ras_nested_recursion import Coverage


@pytest.mark.parametrize('calls', PROFILES)
def test_compressed_committed_groups_preserve_the_expanded_nested_return_sequence(calls):
    state = advance(CommittedStack(), 2, address=OUTER_RETURN)
    for _ in range(calls):
        state = advance(state, 2, address=INNER_RETURN)
    expanded = [OUTER_RETURN, *([INNER_RETURN] * calls)]
    for expected in expanded_returns(calls):
        assert state.projection()['top'] == expanded.pop() == expected
        state = advance(state, 1)
        assert state.projection()['top'] == (expanded[-1] if expanded else 0)
    assert state.head == 0 and len(state.groups) == 1
    with pytest.raises(ValueError, match='bottom/empty'):
        advance(state, 1)


@pytest.mark.parametrize('calls', PROFILES)
def test_semantic_frames_preserve_distinct_outer_identity_after_all_recursive_pops(calls):
    model = RasReference()
    model.advance(Events(2, 2 * OUTER_RETURN))
    model.advance()
    for _ in range(calls):
        model.advance(Events(2, 2 * INNER_RETURN))
        model.advance()
    for expected in expanded_returns(calls):
        assert model.projection['top'] == expected
        model.advance(Events(1))
        model.advance()
    assert len(model.program.frames) == 1 and model.program.head.address == 0


@pytest.mark.parametrize('calls', PROFILES)
@pytest.mark.parametrize('missing', RULES)
def test_every_lifetime_obligation_is_required_before_checked_credit(calls, missing):
    coverage = Coverage(calls)
    for rule in RULES:
        if rule != missing:
            coverage.reached(rule)
    with pytest.raises(AssertionError, match='incomplete'):
        coverage.finish()
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('calls', PROFILES)
def test_only_one_complete_lifetime_can_receive_checked_credit(calls):
    coverage = Coverage(calls)
    for rule in RULES:
        coverage.reached(rule)
    coverage.finish()
    assert coverage.finished and coverage.groups['checked'].coverage == 50
    with pytest.raises(AssertionError):
        coverage.finish()
    with pytest.raises(ValueError):
        coverage.reached(RULES[0])


@pytest.mark.parametrize('calls', (0, 7, 10, True))
def test_unknown_or_aliasing_profile_is_not_a_semantic_boundary(calls):
    with pytest.raises(ValueError):
        expanded_returns(calls)
