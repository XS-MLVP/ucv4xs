from __future__ import annotations

import pytest

from bpuverify.sc.checker.assertions import learn
from bpuverify.sc.case.definitions import PC
from bpuverify.sc.case.definitions import POSITION
from bpuverify.sc.case.definitions import TAGE_COUNTER


@pytest.mark.feature("BPU-SC-001")
async def test_provider_invalid_suppresses_sc_override(sc_agent):
    await sc_agent.reset()
    await learn(sc_agent, 1)
    prediction = await sc_agent.predict(
        PC,
        POSITION,
        TAGE_COUNTER,
        provider_valid=0,
    )
    assert prediction.used == 0


@pytest.mark.feature("BPU-SC-002")
async def test_training_crosses_activation_threshold(sc_agent):
    await sc_agent.reset()
    cold = await sc_agent.predict(PC, POSITION, TAGE_COUNTER)
    learned = await learn(sc_agent, 1)
    assert cold.used == 0
    assert learned.used == 1
    assert learned.meta["sumAboveThres"][0] == 1
