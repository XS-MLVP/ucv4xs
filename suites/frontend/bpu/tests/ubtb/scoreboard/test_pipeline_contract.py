"""Driver acceptance and monitor observations are aligned by Scoreboard."""

from __future__ import annotations

import pytest

from toffee import TransferState
from bpuverify.ubtb.checker.assertions import expected_prediction
from bpuverify.ubtb.checker.assertions import train_taken
from bpuverify.ubtb.case.definitions import DIRECT


@pytest.mark.feature("BPU-UBTB-007")
async def test_back_to_back_lookups_complete_at_declared_latency(ubtb_agent):
    await ubtb_agent.reset()
    await train_taken(ubtb_agent, DIRECT)
    expected = expected_prediction(DIRECT)

    transfers = [
        ubtb_agent.submit_predict(DIRECT.pc, expected=expected)
        for _ in range(4)
    ]
    await ubtb_agent.drain_predictions()

    assert all(transfer.state is TransferState.COMPLETED for transfer in transfers)
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    completed = [transfer.completed_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 8, 2))
    assert completed == [tick + 2 for tick in accepted]
