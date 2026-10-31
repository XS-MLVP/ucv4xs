from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.case.definitions import COLD_STREAM_LENGTH
from suites.frontend.bpu.bpu.case.definitions import PC


@pytest.mark.feature("BPU-INT-001")
async def test_reset_vector_reaches_first_prediction(bpu_agent):
    await bpu_agent.reset(PC)
    transfers, prediction = await bpu_agent.next_prediction(start_pc=PC)
    assert transfers < 64
    assert prediction.start_pc == PC


@pytest.mark.feature("BPU-INT-002")
async def test_cold_prediction_stream_defaults_not_taken(bpu_agent):
    await bpu_agent.reset(PC)
    _, first = await bpu_agent.next_prediction(start_pc=PC)
    predictions = [first] + [
        (await bpu_agent.next_prediction())[1]
        for _ in range(COLD_STREAM_LENGTH - 1)
    ]
    assert all(prediction.taken == 0 for prediction in predictions)
