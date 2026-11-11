"""Independent semantic histories for the new victim-exposure contract."""
from dataclasses import replace

import pytest

from suites.frontend.bpu.testbenches.bpu.model.main_sources import source_entries
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Branch
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Events
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Feedback
from suites.frontend.bpu.testbenches.mbtb.model.semantic import MbtbReference
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Source

PC = 0x40000800


def lookup(model, pc=PC):
    for _ in range(2):
        model.advance(Events(pc=pc, select=True, advance=True, consume=True))
    return model.frame


def learn(model, frame, position, *, kind=3, taken=True, target=None):
    request = Feedback((frame.pc, (frame.pc // 16 + 1) * 16), source_entries(frame),
        (Branch(target if target is not None else PC + 0x800 + position * 8,
                taken, position, kind, mispredict=True),))
    model.advance(Events(feedback=request))
    for _ in range(10):
        model.advance()
    return request


def prepared(model):
    for position in range(1, 7):
        learn(model, lookup(model, PC + position), position,
              kind=1 if position == 1 else 3)
    assert lookup(model).values()['4.position'] == 1
    assert lookup(model, PC + 2).values()['4.position'] == 2


def test_hidden_resident_victim_may_allocate_main_without_retargeting_the_hidden_copy():
    model = MbtbReference()
    prepared(model)
    original = lookup(model)
    assert original.values()['4.position'] == 1
    learn(model, original, 2, target=PC + 0x1234)
    result = lookup(model, PC + 2).values()
    assert any(result[f'{way}.valid'] and result[f'{way}.position'] == 2 and
               result[f'{way}.target'] == PC + 0x1234 for way in range(4))
    assert original.values()['4.position'] == 1


def test_exposed_still_resident_victim_is_retargeted_in_place_without_main_allocation():
    model = MbtbReference()
    prepared(model)
    original = lookup(model, PC + 2)
    before = dict(model.memory)
    learn(model, original, 2, target=PC + 0x1234)
    result = lookup(model, PC + 2).values()
    assert model.memory == before
    assert result['4.position'] == 2 and result['4.target'] == PC + 0x1234


@pytest.mark.parametrize('existing', (False, True))
def test_not_taken_conditional_feedback_cannot_create_or_retype_an_entry(existing):
    model = MbtbReference()
    if existing:
        learn(model, lookup(model), 5, kind=3)
    before = dict(model.memory)
    learn(model, lookup(model), 5, kind=1, taken=False, target=PC + 6)
    assert model.memory == before


def test_nonconditional_false_hit_correction_must_still_invalidate():
    model = MbtbReference()
    learn(model, lookup(model), 5, kind=3)
    learn(model, lookup(model), 5, kind=0, taken=False, target=PC + 6)
    assert not any(lookup(model).values()[f'{way}.valid'] for way in range(5))


def test_stale_victim_metadata_without_residency_does_not_suppress_main_allocation():
    model = MbtbReference()
    # Pure protocol input, explicitly not an integrated-producer history.
    frame = lookup(model)
    sources = [list(row) for row in source_entries(frame)]
    sources[0][4] = Source(True, 5)
    request = Feedback((PC, PC + 16), tuple(tuple(row) for row in sources),
        (Branch(PC + 0x1234, True, 5, 3, mispredict=True),))
    model.advance(Events(feedback=request))
    for _ in range(10):
        model.advance()
    assert lookup(model).values()['3.target'] == PC + 0x1234
