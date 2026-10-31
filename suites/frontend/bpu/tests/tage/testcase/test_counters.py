from __future__ import annotations

import pytest

from suites.frontend.bpu.tage.transaction.types import TageTraining
from suites.frontend.bpu.tage.checker.assertions import allocate
from suites.frontend.bpu.tage.checker.assertions import provider_counter
from suites.frontend.bpu.tage.case.definitions import PC
from suites.frontend.bpu.tage.case.definitions import POSITION
from suites.frontend.bpu.tage.case.definitions import SATURATION_ATTEMPTS


@pytest.mark.feature("BPU-TAGE-003")
async def test_taken_counter_converges_and_saturates(tage_agent):
    await tage_agent.reset()
    prediction = await allocate(tage_agent)
    trace = []
    for _ in range(SATURATION_ATTEMPTS):
        await tage_agent.train(TageTraining(PC, POSITION, 1, 0, prediction.meta))
        prediction = await tage_agent.predict(PC, POSITION, 0)
        trace.append(provider_counter(prediction))
    assert (prediction.valid, prediction.taken) == (1, 1)
    assert trace[-2:] == [7, 7]


@pytest.mark.feature("BPU-TAGE-004")
async def test_not_taken_counter_converges_and_saturates(tage_agent):
    await tage_agent.reset()
    prediction = await allocate(tage_agent)
    trace = []
    for _ in range(SATURATION_ATTEMPTS):
        await tage_agent.train(TageTraining(PC, POSITION, 0, 1, prediction.meta))
        prediction = await tage_agent.predict(PC, POSITION, 1)
        trace.append(provider_counter(prediction))
    assert (prediction.valid, prediction.taken) == (1, 0)
    assert trace[-2:] == [0, 0]
