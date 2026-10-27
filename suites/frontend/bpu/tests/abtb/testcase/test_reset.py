"""AheadBTB SRAM reset and cold metadata."""

from __future__ import annotations

import pytest

from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.case.definitions import DIRECT


@pytest.mark.feature("BPU-ABTB-001")
async def test_reset_completes_before_cold_miss_metadata(abtb_agent):
    waited = await abtb_agent.reset()
    cold = await abtb_agent.predict(DIRECT.pc)

    assert waited < 256
    assert_miss(cold)
    assert cold.meta["valid"] == 1
    assert cold.meta["bankMask"].bit_count() == 1


@pytest.mark.feature("BPU-ABTB-008")
async def test_cold_metadata_tracks_requested_pc_set_index(abtb_agent):
    await abtb_agent.reset()
    for offset in (0, 2, 4, 6):
        pc = DIRECT.pc + offset
        cold = await abtb_agent.predict(pc)
        assert_miss(cold)
        assert cold.meta["setIdx"] == offset // 2, (pc, cold.meta)
        assert cold.meta["bankMask"] == 1, (pc, cold.meta)
