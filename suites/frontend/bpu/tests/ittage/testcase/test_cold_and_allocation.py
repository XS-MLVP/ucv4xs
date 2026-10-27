from __future__ import annotations

import pytest

from bpuverify.ittage.checker.assertions import allocate
from bpuverify.ittage.case.definitions import PC
from bpuverify.ittage.case.definitions import TARGET_A


@pytest.mark.feature("BPU-ITTAGE-001")
async def test_cold_miss_exposes_allocation_metadata(ittage_agent):
    await ittage_agent.reset()
    prediction = await ittage_agent.predict(PC)
    assert prediction.hit == 0
    assert prediction.meta["provider"]["valid"] == 0
    assert prediction.meta["allocate"]["valid"] == 1


@pytest.mark.feature("BPU-ITTAGE-002")
async def test_training_allocates_target_provider(ittage_agent):
    await ittage_agent.reset()
    prediction = await allocate(ittage_agent)
    assert prediction.target == TARGET_A
