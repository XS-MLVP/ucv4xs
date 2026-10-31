from __future__ import annotations

import pytest

from suites.frontend.bpu.sc.checker.assertions import learn


@pytest.mark.feature("BPU-SC-003")
async def test_taken_direction_converges(sc_agent):
    await sc_agent.reset()
    prediction = await learn(sc_agent, 1)
    assert (prediction.used, prediction.taken) == (1, 1)


@pytest.mark.feature("BPU-SC-004")
async def test_not_taken_direction_converges(sc_agent):
    await sc_agent.reset()
    prediction = await learn(sc_agent, 0)
    assert (prediction.used, prediction.taken) == (1, 0)
