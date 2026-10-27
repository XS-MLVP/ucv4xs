"""MicroRAS address and position boundaries."""

from __future__ import annotations

import pytest

from bpuverify.uras.transaction.types import UrasCycle
from bpuverify.uras.checker.assertions import pushed
from bpuverify.uras.case.definitions import BOUNDARIES


@pytest.mark.feature("BPU-URAS-007")
@pytest.mark.parametrize("vector", BOUNDARIES)
async def test_call_target_position_boundaries(uras_agent, vector):
    await uras_agent.reset()
    actual = await uras_agent.cycle(
        UrasCycle(
            s1_fire=1,
            spec_start_pc=vector.start_pc,
            spec_position=vector.position,
            spec_action=2,
        )
    )
    assert actual == pushed(vector)
