"""MicroBTB reset contract."""

from __future__ import annotations

import pytest


@pytest.mark.feature("BPU-UBTB-001")
async def test_reset_reports_prediction_and_training_ready(ubtb_agent):
    await ubtb_agent.reset()

    reset_complete, feedback_ready = ubtb_agent.readiness()
    assert reset_complete is True
    assert feedback_ready is True
