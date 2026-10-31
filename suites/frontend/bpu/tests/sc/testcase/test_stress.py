from __future__ import annotations

import pytest

from suites.frontend.bpu.sc.transaction.types import ScTraining
from suites.frontend.bpu.sc.checker.assertions import learn
from suites.frontend.bpu.sc.case.definitions import PC
from suites.frontend.bpu.sc.case.definitions import POSITION
from suites.frontend.bpu.sc.case.definitions import SATURATION_ATTEMPTS
from suites.frontend.bpu.sc.case.definitions import TAGE_COUNTER


@pytest.mark.feature("BPU-SC-005")
async def test_repeated_training_does_not_wrap_direction(sc_agent):
    await sc_agent.reset()
    prediction = await learn(sc_agent, 1)
    tail = []
    for _ in range(SATURATION_ATTEMPTS):
        await sc_agent.train(ScTraining(PC, POSITION, 1, prediction.meta))
        prediction = await sc_agent.predict(PC, POSITION, TAGE_COUNTER)
        tail.append((prediction.used, prediction.taken))
    assert tail[-8:] == [(1, 1)] * 8


@pytest.mark.feature("BPU-SC-006")
async def test_untrained_pc_and_position_remain_isolated(sc_agent):
    await sc_agent.reset()
    await learn(sc_agent, 1)
    other = await sc_agent.predict(PC + 0x100, POSITION + 1, TAGE_COUNTER)
    assert other.used == 0
