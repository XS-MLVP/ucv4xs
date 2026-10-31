"""MicroTAGE directional counter convergence and saturation."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.checker.assertions import allocate
from suites.frontend.bpu.utage.checker.assertions import counter
from suites.frontend.bpu.utage.case.definitions import PASSING_PC
from suites.frontend.bpu.utage.case.definitions import POSITION
from suites.frontend.bpu.utage.case.definitions import SATURATION_ATTEMPTS


@pytest.mark.feature("BPU-UTAGE-003")
async def test_taken_counter_saturates_without_wrap(utage_agent):
    await utage_agent.reset()
    prediction = await allocate(utage_agent, PASSING_PC, POSITION)
    trace = []
    for _ in range(SATURATION_ATTEMPTS):
        await utage_agent.train(
            UtageTraining(PASSING_PC, POSITION, 1, prediction.meta)
        )
        prediction = await utage_agent.predict(PASSING_PC, POSITION, 0)
        trace.append(counter(prediction))

    assert prediction.taken == 1
    assert trace[-2:] == [7, 7]


@pytest.mark.feature("BPU-UTAGE-004")
async def test_not_taken_counter_saturates_without_wrap(utage_agent):
    await utage_agent.reset()
    prediction = await allocate(utage_agent, PASSING_PC, POSITION)
    trace = []
    for _ in range(SATURATION_ATTEMPTS):
        await utage_agent.train(
            UtageTraining(PASSING_PC, POSITION, 0, prediction.meta)
        )
        prediction = await utage_agent.predict(PASSING_PC, POSITION, 1)
        trace.append(counter(prediction))

    assert prediction.taken == 0
    assert trace[-2:] == [0, 0]
