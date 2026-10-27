from __future__ import annotations

import pytest

from bpuverify.tage.checker.assertions import allocate
from bpuverify.tage.case.definitions import PC
from bpuverify.tage.case.definitions import POSITION


@pytest.mark.feature("BPU-TAGE-001")
async def test_cold_lookup_uses_base_fallback(tage_agent):
    await tage_agent.reset()
    prediction = await tage_agent.predict(PC, POSITION, 0)
    assert prediction.valid == 0
    assert prediction.meta["hasProvider"] == 0
    assert prediction.meta["altOrBasePred"] == 0


@pytest.mark.feature("BPU-TAGE-002")
async def test_mispredict_training_allocates_provider(tage_agent):
    await tage_agent.reset()
    prediction = await allocate(tage_agent)
    assert prediction.provider_counter_valid == 1
