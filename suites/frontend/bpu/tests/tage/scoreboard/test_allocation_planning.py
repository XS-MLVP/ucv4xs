"""Learning forecasts are pure, and agree with independently clocked admission."""
from copy import deepcopy

import pytest

from suites.frontend.bpu.tage.model.semantic import Branch, Context, Entry, Events, Feedback, Read, TageReference


@pytest.mark.parametrize('seed', (*range(1,65),8192,16384,0x1234,32767))
def test_forecast_never_mutates_state_and_matches_the_complete_learning_pipeline(seed):
    model = TageReference()
    model.random = seed  # Pure generator fixture, never a sampled DUT seed.
    feedback = Feedback(0x40000800,Context(),(Branch(4,False,1,True,True,2),))
    before = deepcopy(model.state())
    destination = model.allocation_at_next_accept(feedback)
    assert model.state() == before and not model.memory
    model.advance(Events(feedback=feedback))
    assert not model.offers
    for _ in range(2):
        model.advance()
        assert not model.offers
    model.advance()
    offers = [(table,write.way) for (table,bank),writes in model.offers.items() for write in writes]
    assert offers == [destination]


def test_allocation_uses_invalid_owner_before_overwriting_an_existing_opposite_branch():
    occupied = (Entry(True,0x123,2),Entry())
    empty = (Entry(),Entry())
    read = Read(0,Context(),0,(0,)*8,(empty,empty,occupied,empty,empty,empty,empty,empty),((0,0),)*8)
    assert read.allocation(0,4) == (2,1)
    assert read.allocation(3,4) == (3,0)
    assert read.allocation(8,255) is None


@pytest.mark.parametrize('fault', ('no-reread','pending','maintenance','wrapper'))
def test_forecast_rejects_unsupported_or_nonquiescent_events(fault):
    model = TageReference()
    feedback = Feedback(0,Context(),(Branch(4,False,1,fault!='no-reread',True,2),))
    if fault == 'pending': model.advance(Events(feedback=feedback))
    if fault == 'maintenance': model.aging = True
    if fault == 'wrapper': feedback = object()
    with pytest.raises(ValueError): model.allocation_at_next_accept(feedback)
