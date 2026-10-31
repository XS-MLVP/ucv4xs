"""Long-horizon ITTAGE useful reset without losing the target provider."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ittage.checker.assertions import exhaust_allocation_candidates
from suites.frontend.bpu.ittage.checker.assertions import train_no_allocation_misses


@pytest.mark.feature("BPU-ITTAGE-008")
async def test_no_allocation_tick_saturation_keeps_provider_target(ittage_agent):
    await ittage_agent.reset()
    blocked = await exhaust_allocation_candidates(ittage_agent)
    provider = blocked.meta["provider"]

    # TickCounter is 8 bits. Sustained genuine no-allocation mispredictions
    # traverse positive saturation and start a useful-counter sweep.
    after, last_target = await train_no_allocation_misses(
        ittage_agent, blocked, count=260
    )

    assert after.hit == 1
    assert after.meta["provider"] == provider
    assert after.target == last_target
    assert after.meta["allocate"]["valid"] == 0
