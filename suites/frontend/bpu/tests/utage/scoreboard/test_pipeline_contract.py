"""Scoreboard aligns back-to-back requests with three-cycle responses."""

from __future__ import annotations

import pytest

from toffee import TransferState
from bpuverify.utage.checker.assertions import allocate
from bpuverify.utage.checker.assertions import require_hit
from bpuverify.utage.case.definitions import PASSING_PC
from bpuverify.utage.case.definitions import POSITION


@pytest.mark.feature("BPU-UTAGE-006")
async def test_back_to_back_lookups_complete_at_declared_latency(utage_agent):
    await utage_agent.reset()
    await allocate(utage_agent, PASSING_PC, POSITION)
    transfers = [
        utage_agent.submit_predict(
            PASSING_PC,
            POSITION,
            0,
            expected=require_hit,
        )
        for _ in range(4)
    ]
    await utage_agent.drain_predictions()

    assert all(transfer.state is TransferState.COMPLETED for transfer in transfers)
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    completed = [transfer.completed_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 8, 2))
    # The driver's acceptance event follows its rise-write launch cycle;
    # the sampled response is two additional DUT cycles after acceptance.
    assert completed == [tick + 4 for tick in accepted]
