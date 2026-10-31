"""MicroTAGE result and training metadata form one observation."""

from __future__ import annotations

from suites.frontend.bpu.utage.checker.assertions import allocate
from suites.frontend.bpu.utage.case.definitions import PASSING_PC
from suites.frontend.bpu.utage.case.definitions import POSITION


async def test_monitor_decodes_hit_taken_and_metadata(utage_agent):
    await utage_agent.reset()
    prediction = await allocate(utage_agent, PASSING_PC, POSITION)
    assert prediction.hit == 1
    assert prediction.taken == 1
    assert prediction.meta["abtbResult"][0]["valid"] == 1
