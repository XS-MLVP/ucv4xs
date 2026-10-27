"""Picker binding and write-mode contract for AheadBTB."""

from __future__ import annotations


async def test_lookup_training_and_sideband_are_structurally_bound(abtb_agent):
    interfaces = abtb_agent.ports

    assert abtb_agent.dut.clock.IsImmWrite()
    assert interfaces.control.bits.enable.IsRiseWrite()
    assert interfaces.lookup.bits.start_pc.IsRiseWrite()
    assert interfaces.lookup.bits.new_start_pc.IsRiseWrite()
    assert interfaces.lookup.bits.path_hash.IsRiseWrite()
    assert interfaces.training.valid.IsRiseWrite()
    assert "micro_tage" in interfaces.prediction.bits


async def test_bound_interfaces_have_diagnostic_names(abtb_agent):
    interfaces = abtb_agent.ports
    assert interfaces.control.name == "abtb.control"
    assert interfaces.lookup.name == "abtb.lookup"
    assert interfaces.training.name == "abtb.fast_train"
    assert interfaces.prediction.name == "abtb.prediction"
    assert interfaces.status.name == "abtb.status"
