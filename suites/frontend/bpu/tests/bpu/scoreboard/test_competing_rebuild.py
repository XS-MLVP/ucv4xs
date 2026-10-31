"""Owned normal-event preparation exposes a previously excluded combination.

This is a pure-model admissibility and rejection check, not a DUT verdict or
proof of arbitrary FTQ lifetimes. No internal state or metadata is injected.
"""
from dataclasses import replace

import pytest

from suites.frontend.bpu.bpu.model.pipeline import Redirect
from suites.frontend.bpu.bpu.model.tage.partial_residency import PAIR, PROGRAMS
from suites.frontend.bpu.bpu.model.tage.service import STREAM_PC
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_partial_residency import prepare_program, profile
from tests.tage.scoreboard.test_competing_rebuild import component_state


def test_original_pair_can_compete_after_one_branch_migrates_and_its_peer_is_evicted():
    model, event, anchor, saved, current = prepare_program(PROGRAMS[0])
    source = saved['a-old-1']
    assert profile(model, source) == ((1, 3), ((7, 0, 2, 0), (7, 1, 5, 0)))
    assert profile(model, current['original']) == ((0, 0), ((7, 1, 2, 0), None))
    request = resolution(source, PAIR)
    assert not model.sources.feedback_for(request).reread
    model.advance(replace(quiet(model, event), redirect=Redirect(
        anchor.history, anchor.pc + 4, STREAM_PC, True)))
    for _ in range(8):
        model.advance(event)
    model.advance(replace(event, feedback=request))
    for _ in range(12):
        before = component_state(model.sources.tage)
        try:
            model.advance(event)
        except ValueError as failure:
            assert 'retained destination' in str(failure)
            offered = model.sources.tage.offers[7, 0]
            assert len(offered) == 2 and len({write.row for write in offered}) == 1
            assert len({write.entry.tag for write in offered}) == 2
            assert tuple((write.way, write.entry.counter, write.taken) for write in offered) == (
                (0, 1, False), (1, 6, True))
            assert component_state(model.sources.tage) == before
            return
    pytest.fail('normal owned pair did not reach the declared competing destination')
