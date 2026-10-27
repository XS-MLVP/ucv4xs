from __future__ import annotations

import pytest

from bpuverify.bpu.case.definitions import PC


@pytest.mark.feature("BPU-INT-003")
async def test_prediction_payload_holds_under_backpressure(bpu_agent):
    await bpu_agent.reset(PC)
    snapshot = await bpu_agent.hold_backpressure(cycles=6)
    assert snapshot.prediction_valid == (1, 1)
    assert snapshot.prediction[0] == snapshot.prediction[1]
