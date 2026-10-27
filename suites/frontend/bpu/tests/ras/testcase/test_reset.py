"""RAS reset state."""

from __future__ import annotations

import pytest


@pytest.mark.feature("BPU-RAS-001")
async def test_reset_produces_deterministic_empty_state(ras_agent):
    await ras_agent.reset()
    first = ras_agent.snapshot()
    await ras_agent.reset()
    second = ras_agent.snapshot()
    assert second == first
