from __future__ import annotations

from toffee import TransferState
from suites.frontend.bpu.tage.checker.assertions import allocate
from suites.frontend.bpu.tage.checker.assertions import require_provider
from suites.frontend.bpu.tage.case.definitions import PC
from suites.frontend.bpu.tage.case.definitions import POSITION


async def test_back_to_back_lookups_complete_two_cycles_after_acceptance(tage_agent):
    await tage_agent.reset()
    await allocate(tage_agent)
    transfers = [
        tage_agent.submit_predict(PC, POSITION, 0, expected=require_provider)
        for _ in range(4)
    ]
    await tage_agent.drain_predictions()
    assert all(transfer.state is TransferState.COMPLETED for transfer in transfers)
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert [transfer.completed_event.tick for transfer in transfers] == [
        tick + 4 for tick in accepted
    ]
