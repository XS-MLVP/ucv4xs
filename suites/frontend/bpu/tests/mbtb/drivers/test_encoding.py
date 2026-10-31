"""MainBTB lookup transaction encoding."""

from __future__ import annotations

from suites.frontend.bpu.mbtb.transaction.types import MbtbLookup


async def test_lookup_encoder_maps_pipeline_controls(mbtb_agent):
    # S0 selects and starts the SRAM read; S1 and S2 are separate token
    # drivers so that a continuous S2 fire cannot clean a stale read.
    assert mbtb_agent.lookup_driver.encoder(MbtbLookup(0x4000_0800)) == {
        "s0_fire": 1,
        "s3_fire": 0,
        "victim_taken": (0, 0),
        "start_pc": 0x4000_0800,
    }
    assert mbtb_agent.advance_driver.encoder(None) == {"fire": 1}
    assert mbtb_agent.consume_driver.encoder(None) == {
        "fire": int(not mbtb_agent._defer_multi_hit_cleanup)}
