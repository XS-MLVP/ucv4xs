"""Port mapping is qualified separately from the domain reference."""
import pytest

from suites.vector.vagq.manager.encoding import decode, encode
from suites.vector.vagq.manager.types import Beat, Idle, Offer

pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_semantic_controls_have_explicit_independent_wire_answers():
    beat = Beat(Offer(3), released=frozenset({0, 7}), recovery=frozenset(),
                walked=frozenset({2, 4}))
    assert encode(beat) == dict(reqValid=1, reqCount=3, releaseMask=0x81,
        redirect=1, bitMapMask=0, walkValid=1, walkMask=0x14)
    assert decode(dict(reqValid=0, reqCount=15, releaseMask=2, redirect=0,
                       bitMapMask=255, walkValid=1, walkMask=0)) == Beat(
                           Idle(15), released=frozenset({1}), walked=frozenset())


def test_monitor_rejects_live_mutation_of_a_frozen_domain_snapshot():
    from dataclasses import FrozenInstanceError
    from suites.vector.vagq.manager.types import Allocation, Boundary, Cycle
    sample = Boundary(False, Beat(Offer(1)), Allocation(1, 0, 1))
    cycle = Cycle(1, sample, sample)
    with pytest.raises(FrozenInstanceError):
        cycle.after.beat = Beat()
