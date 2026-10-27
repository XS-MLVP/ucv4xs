"""Backend phase association is a monitor responsibility, not a golden algorithm."""
import pytest
from toffee import XEvent, XEventKind, XPhase

from vagqverify.manager.monitor import CycleAssembler
from vagqverify.manager.types import Allocation, Beat, Boundary

pytestmark = pytest.mark.toffee_functional_coverage(False)
IDLE = Boundary(False, Beat(), Allocation())


def event(tick, phase):
    return XEvent(tick, tick, phase, XEventKind.CLOCK_RISE)


def test_freeze_and_pair_exactly_adjacent_boundaries():
    monitor = CycleAssembler()
    assert monitor.accept(event(1, XPhase.DRIVE_STABLE), IDLE) is None
    cycle = monitor.accept(event(2, XPhase.RISING_STABLE), IDLE)
    assert cycle.index == 1 and cycle.before is IDLE and cycle.after is IDLE
    monitor.finish()


def test_missing_duplicate_wrong_phase_and_unfinished_boundaries_fail():
    monitor = CycleAssembler()
    with pytest.raises(AssertionError, match='no complete'):
        monitor.finish()
    with pytest.raises(AssertionError, match='preceding preedge'):
        monitor.accept(event(2, XPhase.RISING_STABLE), IDLE)
    monitor.accept(event(1, XPhase.DRIVE_STABLE), IDLE)
    with pytest.raises(AssertionError, match='duplicate'):
        monitor.accept(event(1, XPhase.DRIVE_STABLE), IDLE)
    with pytest.raises(AssertionError, match='unsupported'):
        monitor.accept(event(2, XPhase.FALLING_STABLE), IDLE)
    with pytest.raises(AssertionError, match='preceding preedge'):
        monitor.accept(event(4, XPhase.RISING_STABLE), IDLE)
    with pytest.raises(AssertionError, match='unconsumed'):
        monitor.finish()
    monitor.accept(event(2, XPhase.RISING_STABLE), IDLE)
    with pytest.raises(AssertionError, match='missing preedge'):
        monitor.accept(event(5, XPhase.DRIVE_STABLE), IDLE)
