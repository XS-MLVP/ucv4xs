from __future__ import annotations


async def test_sc_lookup_training_and_result_bundles_use_rise_write(sc_agent):
    interfaces = sc_agent.ports
    assert sc_agent.dut.clock.IsImmWrite()
    assert interfaces.control.bits.enable.IsRiseWrite()
    assert interfaces.lookup.bits.start_pc.IsRiseWrite()
    assert interfaces.training.valid.IsRiseWrite()
    assert "taken" in interfaces.prediction.bits
    assert "used" in interfaces.prediction.bits
    from suites.frontend.bpu.models.configuration import RESULT_SLOTS
    assert len(interfaces.prediction.bits.takens) == RESULT_SLOTS
    assert len(interfaces.prediction.bits.useds) == RESULT_SLOTS
