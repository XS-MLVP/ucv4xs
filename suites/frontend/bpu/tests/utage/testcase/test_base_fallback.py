"""MicroTAGE miss emits no correction but carries the AheadBTB base bias."""

from __future__ import annotations

import pytest

from bpuverify.utage.case.definitions import PASSING_PC
from bpuverify.utage.case.definitions import POSITION


@pytest.mark.feature("BPU-UTAGE-005")
async def test_cold_miss_preserves_base_direction_in_metadata(utage_agent):
    await utage_agent.reset()
    not_taken = await utage_agent.predict(PASSING_PC, POSITION, 0)
    taken = await utage_agent.predict(PASSING_PC + 0x20, POSITION, 1)
    assert (not_taken.hit, not_taken.taken) == (0, 0)
    assert (taken.hit, taken.taken) == (0, 0)
    assert not_taken.meta["abtbResult"][0]["baseTaken"] == 0
    assert taken.meta["abtbResult"][0]["baseTaken"] == 1
