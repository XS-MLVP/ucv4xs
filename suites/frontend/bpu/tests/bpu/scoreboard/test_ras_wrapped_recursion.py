"""Bounded semantic oracles and closure controls; no DUT coverage credit."""
import pytest

from suites.frontend.bpu.ras.model.model import advance
from suites.frontend.bpu.bpu.model.ras.wrapped_recursion import (
    PREFIX, INNER_RETURN, PARENT_RETURN, SURVIVING_TOP, PROFILES, RULES,
    committed, return_targets, validate)
from suites.frontend.bpu.bpu.coverage.ras_wrapped_recursion import Coverage


@pytest.mark.parametrize('calls', PROFILES)
def test_full_capacity_wrap_and_recursion_have_independent_lifetime_boundaries(calls):
    state = committed(calls)
    assert (state.head, state.projection()['sctr']) == ((0, 7) if calls == 8 else (1, 0))
    assert len(state.evicted) == (1 if calls == 8 else 2)
    assert state.evicted[0].address == 0  # Only the reset sentinel at first wrap.
    if calls == 9:
        assert state.evicted[1].address == PREFIX[0] + 16


@pytest.mark.parametrize('calls', PROFILES)
def test_all_recursive_frames_then_one_parent_return_preserve_only_retained_older_callers(calls):
    state = committed(calls)
    for target in return_targets(calls):
        assert state.projection()['top'] == target
        state = advance(state, 1)
    expected = committed(calls, returned=True)
    assert state == expected and state.projection()['top'] == SURVIVING_TOP
    assert tuple(group.address for group in state.groups) == tuple(
        pc + 16 for pc in PREFIX[(1 if calls == 9 else 0):-1])
    assert return_targets(calls) == (INNER_RETURN,) * calls + (PARENT_RETURN,)


@pytest.mark.parametrize('calls', PROFILES)
@pytest.mark.parametrize('missing', RULES)
def test_partial_wrap_or_partial_unwind_has_no_checked_credit(calls, missing):
    coverage = Coverage(calls)
    for rule in RULES:
        if rule != missing:
            coverage.reached(rule)
    with pytest.raises(AssertionError):
        coverage.finish()
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('calls', (0, 7, True))
def test_not_a_declared_repeat_boundary_is_rejected(calls):
    with pytest.raises(ValueError):
        validate(calls)
