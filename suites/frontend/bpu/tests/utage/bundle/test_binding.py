"""Picker binding and write-mode contract for MicroTAGE."""

from __future__ import annotations


async def test_lookup_training_and_prediction_bundles_are_bound(utage_agent):
    interfaces = utage_agent.ports
    assert utage_agent.dut.clock.IsImmWrite()
    assert interfaces.control.bits.enable.IsRiseWrite()
    assert interfaces.lookup.bits.start_pc.IsRiseWrite()
    assert interfaces.lookup.bits.ahead_btb.result[0].valid.IsRiseWrite()
    assert interfaces.training.valid.IsRiseWrite()
    assert "hit" in interfaces.prediction.bits
    assert "taken" in interfaces.prediction.bits
    assert len(interfaces.prediction.bits.hits) == 4
    assert len(interfaces.prediction.bits.takens) == 4
    assert "meta" in interfaces.prediction.bits
