"""Picker binding and write-mode contract for MainBTB."""

from __future__ import annotations


async def test_lookup_and_training_interfaces_use_rise_write(mbtb_agent):
    interfaces = mbtb_agent.ports
    assert mbtb_agent.dut.clock.IsImmWrite()
    assert interfaces.control.bits.enable.IsRiseWrite()
    assert interfaces.lookup.bits.start_pc.IsRiseWrite()
    assert interfaces.training.valid.IsRiseWrite()
    assert interfaces.training.bits.start_pc0.IsRiseWrite()


async def test_prediction_binding_contains_entries_and_training_metadata(mbtb_agent):
    assert "entries" in mbtb_agent.ports.prediction.bits
    assert "meta_entries" in mbtb_agent.ports.prediction.bits
