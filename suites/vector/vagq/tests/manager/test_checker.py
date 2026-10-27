"""Checker qualification uses semantic cycles, without native event construction."""
from dataclasses import replace

import pytest
from toffee import ScoreboardMismatch

from vagqverify.manager.checker import ManagerChecker
from vagqverify.manager.coverage import ManagerCoverage
from vagqverify.manager.types import Allocation, Beat, Boundary, Cycle, Offer

pytestmark = pytest.mark.toffee_functional_coverage(False)
IDLE = Boundary(False, Beat(), Allocation())
RESET = Boundary(True, Beat(), Allocation())


def initialized(coverage=None):
    checker = ManagerChecker(coverage)
    checker.observe(Cycle(1, RESET, RESET))
    return checker


@pytest.mark.parametrize('field,value', [('valid', 0), ('start', 3), ('mask', 2)])
@pytest.mark.parametrize('boundary', ['before', 'after'])
def test_each_output_corruption_is_rejected_and_never_resynchronizes(field, value, boundary):
    checker = initialized()
    offer = Boundary(False, Beat(Offer(1)), Allocation(1, 0, 1))
    bad = replace(offer, allocation=replace(offer.allocation, **{field: value}))
    cycle = Cycle(2, bad, IDLE) if boundary == 'before' else Cycle(2, IDLE, bad)
    with pytest.raises(ScoreboardMismatch):
        checker.observe(cycle)
    assert checker.state.occupied == frozenset()
    assert checker.board.status.failed == 1
    assert checker.checked_cycles == 1


@pytest.mark.parametrize('index', [1, 3])
def test_duplicate_or_missing_semantic_cycle_fails(index):
    checker = initialized()
    with pytest.raises(AssertionError, match='missing, duplicated or reordered'):
        checker.observe(Cycle(index, IDLE, IDLE))


@pytest.mark.parametrize('boundary', ['before', 'after'])
def test_failure_does_not_receive_checked_coverage_credit(boundary):
    coverage = ManagerCoverage(capture=False)
    checker = initialized(coverage)
    before = coverage.groups['checked'].report()
    bad = Boundary(False, Beat(Offer(1)), Allocation())
    with pytest.raises(ScoreboardMismatch):
        checker.observe(Cycle(2, bad, IDLE) if boundary == 'before' else Cycle(2, IDLE, bad))
    assert coverage.groups['checked'].report() == before


def test_no_reset_and_no_observation_are_not_success():
    checker = ManagerChecker()
    with pytest.raises(AssertionError, match='observed reset'):
        checker.observe(Cycle(1, IDLE, IDLE))
    with pytest.raises(AssertionError, match='no checked'):
        checker.finish()
