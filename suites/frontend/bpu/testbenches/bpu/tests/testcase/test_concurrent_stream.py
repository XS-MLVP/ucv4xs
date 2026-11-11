from __future__ import annotations

import pytest

from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuTraining
from suites.frontend.bpu.testbenches.bpu.model.vectors import PC
from suites.frontend.bpu.testbenches.bpu.model.vectors import POSITION
from suites.frontend.bpu.testbenches.bpu.model.vectors import TARGET


@pytest.mark.feature("BPU-INT-009")
async def test_prediction_stream_continues_while_training_is_accepted(bpu_agent):
    await bpu_agent.reset(PC)
    transaction = await bpu_agent.next_transaction(start_pc=PC)

    activity = await bpu_agent.train_during_stream(
        BpuTraining(PC, POSITION, TARGET, transaction.meta.resolve),
        predictions=16,
    )

    assert len(activity.predictions) == 16
    assert activity.prediction_ticks == tuple(sorted(activity.prediction_ticks))
    assert len(set(activity.prediction_ticks)) == 16
    assert activity.prediction_ticks[0] <= activity.training_tick
    assert activity.training_tick <= activity.prediction_ticks[-1]
