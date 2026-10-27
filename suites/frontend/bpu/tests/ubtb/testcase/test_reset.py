"""MicroBTB reset contract."""

from __future__ import annotations

import pytest


@pytest.mark.feature("BPU-UBTB-001")
async def test_reset_reports_prediction_and_training_ready(ubtb_agent):
    await ubtb_agent.reset()

    status = ubtb_agent.ports.status.bits.sample()
    assert status.reset_done.as_int() == 1
    assert status.train_ready.as_int() == 1
