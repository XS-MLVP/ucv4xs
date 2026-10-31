from __future__ import annotations

from suites.frontend.bpu.tage.checker.assertions import allocate
from suites.frontend.bpu.tage.case.definitions import PC
from suites.frontend.bpu.tage.case.definitions import POSITION


async def test_monitor_decodes_provider_and_counter_valid(tage_agent):
    await tage_agent.reset()
    prediction = await allocate(tage_agent)
    assert prediction.meta["hasProvider"] == 1
    assert prediction.provider_counter_valid == 1
