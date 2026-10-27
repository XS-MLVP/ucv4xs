"""MainBTB lookup transaction encoding."""

from __future__ import annotations

from bpuverify.mbtb.transaction.types import MbtbLookup


async def test_lookup_encoder_maps_pipeline_controls(mbtb_agent):
    assert mbtb_agent.lookup_driver.encoder(MbtbLookup(0x4000_0800)) == {
        "s0_fire": 1,
        "s1_fire": 1,
        "s2_fire": 1,
        "start_pc": 0x4000_0800,
    }
