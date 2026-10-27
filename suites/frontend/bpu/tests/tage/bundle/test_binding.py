from __future__ import annotations


async def test_tage_transaction_bundles_use_rise_write(tage_agent):
    interfaces = tage_agent.ports
    assert tage_agent.dut.clock.IsImmWrite()
    assert interfaces.control.bits.enable.IsRiseWrite()
    assert interfaces.lookup.bits.start_pc.IsRiseWrite()
    assert interfaces.training.valid.IsRiseWrite()
    assert "provider_counter_valid" in interfaces.prediction.bits
    assert len(interfaces.prediction.bits.taken_vec) == 4
    assert len(interfaces.prediction.bits.meta_vec) == 4
    assert len(interfaces.prediction.bits.provider_counter_valid_vec) == 4
