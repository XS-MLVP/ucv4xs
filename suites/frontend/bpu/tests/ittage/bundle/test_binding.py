from __future__ import annotations


async def test_lookup_training_and_prediction_bundles_use_rise_write(ittage_agent):
    interfaces = ittage_agent.ports
    assert ittage_agent.dut.clock.IsImmWrite()
    assert interfaces.control.bits.enable.IsRiseWrite()
    assert interfaces.lookup.bits.start_pc.IsRiseWrite()
    assert interfaces.training.valid.IsRiseWrite()
    assert "target" in interfaces.prediction.bits
    assert "meta" in interfaces.prediction.bits
