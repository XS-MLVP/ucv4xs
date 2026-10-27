from __future__ import annotations


async def test_sc_lookup_training_and_result_bundles_use_rise_write(sc_agent):
    interfaces = sc_agent.ports
    assert sc_agent.dut.clock.IsImmWrite()
    assert interfaces.control.bits.enable.IsRiseWrite()
    assert interfaces.lookup.bits.start_pc.IsRiseWrite()
    assert interfaces.training.valid.IsRiseWrite()
    assert "taken" in interfaces.prediction.bits
    assert "used" in interfaces.prediction.bits
    assert len(interfaces.prediction.bits.takens) == 4
    assert len(interfaces.prediction.bits.useds) == 4
