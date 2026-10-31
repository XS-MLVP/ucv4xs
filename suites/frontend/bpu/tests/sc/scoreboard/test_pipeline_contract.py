from __future__ import annotations

from toffee import TransferState
from suites.frontend.bpu.sc.checker.assertions import learn
from suites.frontend.bpu.sc.checker.assertions import require_used
from suites.frontend.bpu.sc.case.definitions import PC
from suites.frontend.bpu.sc.case.definitions import POSITION
from suites.frontend.bpu.sc.case.definitions import TAGE_COUNTER


async def test_back_to_back_sc_lookups_overlap_and_complete_at_s2(sc_agent):
    await sc_agent.reset()
    await learn(sc_agent, 1)
    transfers = [
        sc_agent.submit_predict(
            PC,
            POSITION,
            TAGE_COUNTER,
            expected=require_used,
        )
        for _ in range(4)
    ]
    await sc_agent.drain_predictions()
    assert all(transfer.state is TransferState.COMPLETED for transfer in transfers)
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 8, 2))
    assert [transfer.completed_event.tick for transfer in transfers] == [
        tick + 2 for tick in accepted
    ]
