from __future__ import annotations

import pytest

from bpuverify.ittage.transaction.types import IttageTraining
from bpuverify.ittage.checker.assertions import allocate
from bpuverify.ittage.case.definitions import MAX_UPDATE_ATTEMPTS
from bpuverify.ittage.case.definitions import PC
from bpuverify.ittage.case.definitions import POSITION
from bpuverify.ittage.case.definitions import TARGET_A
from bpuverify.ittage.case.definitions import TARGET_B


@pytest.mark.feature("BPU-ITTAGE-003")
async def test_provider_target_and_confidence_update(ittage_agent):
    await ittage_agent.reset()
    prediction = await allocate(ittage_agent)
    await ittage_agent.train(
        IttageTraining(PC, POSITION, TARGET_A, prediction.meta, 0)
    )
    prediction = await ittage_agent.predict(PC)
    confidence_trace = []
    for _ in range(MAX_UPDATE_ATTEMPTS):
        await ittage_agent.train(
            IttageTraining(PC, POSITION, TARGET_B, prediction.meta, 1)
        )
        prediction = await ittage_agent.predict(PC)
        confidence_trace.append(prediction.meta["providerCnt_value"])
        if prediction.hit and prediction.target == TARGET_B:
            break

    assert prediction.hit == 1
    assert prediction.target == TARGET_B
    assert all(0 <= value <= 3 for value in confidence_trace)
