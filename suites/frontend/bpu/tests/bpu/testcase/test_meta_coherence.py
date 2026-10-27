from __future__ import annotations

import pytest

from bpuverify.bpu.transaction.types import BpuStage1Source
from bpuverify.bpu.case.definitions import PC


@pytest.mark.feature("BPU-INT-007")
async def test_prediction_and_metadata_channels_advance_as_pairs(bpu_agent):
    await bpu_agent.reset(PC)
    transactions = [await bpu_agent.next_transaction() for _ in range(4)]

    assert all(item.meta_tick == item.prediction_tick + 4 for item in transactions)
    assert all(item.meta.resolve and item.meta.redirect for item in transactions)
    assert all(
        (
            item.meta.perf.start_pc,
            item.meta.perf.s1_target,
            item.meta.perf.s1_taken,
            item.meta.perf.s1_position,
            item.meta.perf.s1_source,
        )
        == (
            item.prediction.start_pc,
            item.prediction.target,
            item.prediction.taken,
            item.prediction.position,
            BpuStage1Source.FALLTHROUGH,
        )
        for item in transactions
    )
