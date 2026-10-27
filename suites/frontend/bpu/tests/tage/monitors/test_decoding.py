from __future__ import annotations

from bpuverify.tage.checker.assertions import allocate
from bpuverify.tage.case.definitions import PC
from bpuverify.tage.case.definitions import POSITION


async def test_monitor_decodes_provider_and_counter_valid(tage_agent):
    await tage_agent.reset()
    prediction = await allocate(tage_agent)
    assert prediction.meta["hasProvider"] == 1
    assert prediction.provider_counter_valid == 1
