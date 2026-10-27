from __future__ import annotations

import pytest

from bpuverify.ittage.transaction.types import IttageTraining
from bpuverify.ittage.checker.assertions import allocate
from bpuverify.ittage.case.definitions import PC
from bpuverify.ittage.case.definitions import POSITION
from bpuverify.ittage.case.definitions import TARGET_A
from bpuverify.ittage.case.definitions import TARGET_B


@pytest.mark.feature("BPU-ITTAGE-005")
async def test_unconfident_provider_falls_back_to_alternate(ittage_agent):
    await ittage_agent.reset()
    first = await allocate(ittage_agent)

    await ittage_agent.train(
        IttageTraining(PC, POSITION, TARGET_B, first.meta, 1)
    )
    layered = await ittage_agent.predict(PC)
    assert layered.hit == 1
    assert layered.target == TARGET_B
    assert layered.meta["provider"]["valid"] == 1
    assert layered.meta["altProvider"]["valid"] == 1
    assert layered.meta["altDiffers"] == 1

    alternate = layered
    confidence = [layered.meta["providerCnt_value"]]
    for _ in range(3):
        await ittage_agent.train(
            IttageTraining(PC, POSITION, TARGET_A, alternate.meta, 0)
        )
        alternate = await ittage_agent.predict(PC)
        confidence.append(alternate.meta["providerCnt_value"])
        if alternate.target == TARGET_A:
            break

    assert alternate.hit == 1
    assert alternate.target == TARGET_A
    assert alternate.meta["provider"]["valid"] == 1
    assert alternate.meta["altProvider"]["valid"] == 1
    assert confidence == sorted(confidence, reverse=True)
    assert confidence[-1] == 0
