"""RAS state monitor preserves top and structured redirect metadata."""

from __future__ import annotations


async def test_snapshot_decodes_redirect_metadata(ras_agent):
    await ras_agent.reset()
    state = ras_agent.snapshot()
    assert isinstance(state.top, int)
    assert set(state.redirect_meta) >= {"ssp", "sctr", "tosr", "tosw", "nos"}
