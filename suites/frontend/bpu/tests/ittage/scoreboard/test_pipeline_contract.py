from __future__ import annotations

import pytest

from toffee import TransferState
from bpuverify.ittage.checker.assertions import allocate
from bpuverify.ittage.checker.assertions import require_hit
from bpuverify.ittage.case.definitions import PC


@pytest.mark.feature("BPU-ITTAGE-006")
async def test_back_to_back_lookups_complete_three_cycles_after_acceptance(ittage_agent):
    await ittage_agent.reset()
    await allocate(ittage_agent)
    transfers = [
        ittage_agent.submit_predict(PC, expected=require_hit) for _ in range(4)
    ]
    await ittage_agent.drain_predictions()
    assert all(transfer.state is TransferState.COMPLETED for transfer in transfers)
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert [transfer.completed_event.tick for transfer in transfers] == [
        tick + 6 for tick in accepted
    ]
