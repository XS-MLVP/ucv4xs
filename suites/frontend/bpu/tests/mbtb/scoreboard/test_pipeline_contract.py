"""Scoreboard aligns back-to-back requests after driver acceptance."""

from __future__ import annotations

import pytest

from toffee import TransferState
from bpuverify.mbtb.checker.assertions import assert_vector_hit
from bpuverify.mbtb.checker.assertions import train
from bpuverify.mbtb.case.definitions import DIRECT
from bpuverify.mbtb.case.definitions import PIPELINE_REQUESTS


@pytest.mark.feature("BPU-MBTB-007")
async def test_back_to_back_lookups_complete_at_declared_latency(mbtb_agent):
    await mbtb_agent.reset()
    cold = await mbtb_agent.predict(DIRECT.pc)
    await train(mbtb_agent, DIRECT, cold.meta_entries)

    transfers = [
        mbtb_agent.submit_predict(
            DIRECT.pc,
            expected=lambda actual: assert_vector_hit(actual, DIRECT),
        )
        for _ in range(PIPELINE_REQUESTS)
    ]
    await mbtb_agent.drain_predictions()

    assert all(transfer.state is TransferState.COMPLETED for transfer in transfers)
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    completed = [transfer.completed_event.tick for transfer in transfers]
    assert accepted == list(
        range(accepted[0], accepted[0] + 2 * PIPELINE_REQUESTS, 2)
    )
    assert completed == [tick + 4 for tick in accepted]
