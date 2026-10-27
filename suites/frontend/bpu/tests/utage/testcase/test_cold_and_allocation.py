"""MicroTAGE cold metadata and first allocation."""

from __future__ import annotations

import pytest

from bpuverify.utage.checker.assertions import allocate
from bpuverify.utage.case.definitions import PASSING_PC
from bpuverify.utage.case.definitions import POSITION


@pytest.mark.feature("BPU-UTAGE-001")
async def test_cold_miss_contains_allocation_metadata(utage_agent):
    await utage_agent.reset()
    prediction = await utage_agent.predict(PASSING_PC, POSITION, 0)
    entry = prediction.meta["abtbResult"][0]
    assert prediction.hit == 0
    assert entry["valid"] == 1
    assert entry["cfiPosition"] == POSITION


@pytest.mark.feature("BPU-UTAGE-002")
async def test_first_training_allocates_a_hit(utage_agent):
    await utage_agent.reset()
    await allocate(utage_agent, PASSING_PC, POSITION)
