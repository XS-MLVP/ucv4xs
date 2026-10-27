from __future__ import annotations

import pytest


async def test_control_driver_tracks_global_enable_and_ready(bpu_agent):
    await bpu_agent.reset(0x4000_0800)
    await bpu_agent.set_enabled(False)
    disabled = bpu_agent.ports.control.bits.sample()
    assert disabled.ubtb_enable.as_int() == 0
    assert disabled.tage_enable.as_int() == 0
    assert disabled.ras_enable.as_int() == 0
    await bpu_agent.set_ready(prediction=False, meta=False)
    stalled = bpu_agent.ports.control.bits.sample()
    assert stalled.prediction_ready.as_int() == 0
    assert stalled.meta_ready.as_int() == 0


async def test_control_driver_can_gate_early_predictors_independently(bpu_agent):
    await bpu_agent.reset(0x4000_0800)
    await bpu_agent.configure_predictors(ubtb=False, abtb=False)
    control = bpu_agent.ports.control.bits.sample()
    assert control.ubtb_enable.as_int() == 0
    assert control.abtb_enable.as_int() == 0
    assert control.mbtb_enable.as_int() == 1
    with pytest.raises(ValueError, match="unknown BPU predictor"):
        await bpu_agent.configure_predictors(not_a_predictor=False)
