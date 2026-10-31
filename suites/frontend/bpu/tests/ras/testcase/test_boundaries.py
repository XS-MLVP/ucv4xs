"""RAS empty and speculative-queue boundary behavior."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ras.checker.assertions import expected_top
from suites.frontend.bpu.ras.checker.assertions import pop
from suites.frontend.bpu.ras.checker.assertions import push
from suites.frontend.bpu.ras.case.definitions import unique_calls


@pytest.mark.feature("BPU-RAS-005")
async def test_empty_pop_preserves_observable_top(ras_agent):
    await ras_agent.reset()
    initial = ras_agent.snapshot()
    assert (await pop(ras_agent)).top == initial.top


@pytest.mark.feature("BPU-RAS-006")
async def test_near_overflow_guard_stops_accepting_unique_pushes(ras_agent):
    await ras_agent.reset()
    accepted = []
    for vector in unique_calls():
        state = await push(ras_agent, vector)
        accepted.append(state.top == expected_top(vector))

    first_rejected = accepted.index(False)
    assert 0 < first_rejected < len(accepted)
    assert not any(accepted[first_rejected:])
