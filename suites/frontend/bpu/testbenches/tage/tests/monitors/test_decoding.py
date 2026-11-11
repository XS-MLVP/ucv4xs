from __future__ import annotations

from suites.frontend.bpu.testbenches.tage.checker.assertions import allocate
from suites.frontend.bpu.testbenches.tage.model.vectors import PC
from suites.frontend.bpu.testbenches.tage.model.vectors import POSITION


async def test_monitor_decodes_provider_and_counter_valid(tage_agent):
    await tage_agent.reset()
    prediction = await allocate(tage_agent)
    assert prediction.meta["hasProvider"] == 1
    assert prediction.provider_counter_valid == 1
