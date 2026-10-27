"""Picker binding and write-mode contract for MicroRAS."""

from __future__ import annotations


async def test_cycle_stimulus_and_result_bundles_are_bound(uras_agent):
    interfaces = uras_agent.ports
    assert uras_agent.dut.clock.IsImmWrite()
    assert interfaces.stimulus.bits.enable.IsRiseWrite()
    assert interfaces.stimulus.bits.s1_fire.IsRiseWrite()
    assert interfaces.stimulus.bits.s2_valid.IsRiseWrite()
    assert interfaces.stimulus.bits.s3_valid.IsRiseWrite()
    assert "usable" in interfaces.result.bits
    assert "target" in interfaces.result.bits
