"""Picker binding and write-mode contract for RAS."""

from __future__ import annotations


async def test_speculative_redirect_and_state_interfaces_are_bound(ras_agent):
    interfaces = ras_agent.ports
    assert ras_agent.dut.clock.IsImmWrite()
    assert interfaces.speculative.valid.IsRiseWrite()
    assert interfaces.speculative.bits.action.IsRiseWrite()
    assert interfaces.redirect.valid.IsRiseWrite()
    assert "top" in interfaces.state.bits
    assert "redirect_meta" in interfaces.state.bits
