from __future__ import annotations


async def test_tage_transaction_bundles_use_rise_write(tage_agent):
    interfaces = tage_agent.ports
    assert tage_agent.dut.clock.IsImmWrite()
    assert interfaces.control.bits.enable.IsRiseWrite()
    assert interfaces.lookup.bits.start_pc.IsRiseWrite()
    assert interfaces.training.valid.IsRiseWrite()
    from suites.frontend.bpu.models.configuration import RESULT_SLOTS
    assert "provider_counter_valid" in interfaces.prediction.bits
    assert len(interfaces.prediction.bits.taken_vec) == RESULT_SLOTS
    assert len(interfaces.prediction.bits.meta_vec) == RESULT_SLOTS
    assert len(interfaces.prediction.bits.provider_counter_valid_vec) == RESULT_SLOTS
