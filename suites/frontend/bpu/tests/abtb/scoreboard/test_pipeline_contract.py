"""Scoreboard aligns back-to-back requests after driver acceptance."""

from __future__ import annotations

import pytest

from toffee import TransferState
from bpuverify.abtb.checker.assertions import assert_vector_hit
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import TRAINING_VECTORS


@pytest.mark.feature("BPU-ABTB-006")
async def test_back_to_back_lookups_complete_at_declared_latency(abtb_agent):
    await abtb_agent.reset()
    for vector in TRAINING_VECTORS:
        cold = await abtb_agent.predict(vector.pc)
        await train_taken(abtb_agent, vector, cold.meta)

    transfers = [
        abtb_agent.submit_predict(
            vector.pc,
            expected=lambda actual, vector=vector: assert_vector_hit(actual, vector),
        )
        for vector in TRAINING_VECTORS
    ]
    await abtb_agent.drain_predictions()

    assert all(transfer.state is TransferState.COMPLETED for transfer in transfers)
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    completed = [transfer.completed_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 6, 2))
    assert completed == [tick + 4 for tick in accepted]
