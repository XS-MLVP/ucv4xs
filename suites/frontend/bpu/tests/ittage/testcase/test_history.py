"""Same fetch PC must not conflate different folded-path contexts."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ittage.transaction.types import IttageTraining
from suites.frontend.bpu.ittage.case.definitions import PC
from suites.frontend.bpu.ittage.case.definitions import POSITION
from suites.frontend.bpu.ittage.case.definitions import TARGET_A
from suites.frontend.bpu.ittage.case.definitions import TARGET_B


@pytest.mark.feature("BPU-ITTAGE-009")
async def test_same_pc_different_folded_history_has_independent_targets(ittage_agent):
    await ittage_agent.reset()
    history_a, history_b = 0, 0b0100

    cold_a = await ittage_agent.predict(PC, folded_history=history_a)
    assert cold_a.hit == 0 and cold_a.meta["allocate"]["valid"] == 1
    await ittage_agent.train(
        IttageTraining(PC, POSITION, TARGET_A, cold_a.meta, 1, history_a)
    )
    trained_a = await ittage_agent.predict(PC, folded_history=history_a)
    assert trained_a.hit == 1 and trained_a.target == TARGET_A

    cold_b = await ittage_agent.predict(PC, folded_history=history_b)
    assert cold_b.hit == 0 and cold_b.meta["allocate"]["valid"] == 1
    await ittage_agent.train(
        IttageTraining(PC, POSITION, TARGET_B, cold_b.meta, 1, history_b)
    )
    trained_b = await ittage_agent.predict(PC, folded_history=history_b)
    assert trained_b.hit == 1 and trained_b.target == TARGET_B

    still_a = await ittage_agent.predict(PC, folded_history=history_a)
    assert still_a.hit == 1 and still_a.target == TARGET_A

    histories = (history_a, history_b, history_a, history_b)
    transfers = [
        ittage_agent.submit_predict(PC, folded_history=history)
        for history in histories
    ]
    await ittage_agent.drain_predictions()
    results = [await transfer for transfer in transfers]
    assert [(result.hit, result.target) for result in results] == [
        (1, TARGET_A), (1, TARGET_B), (1, TARGET_A), (1, TARGET_B)
    ], [
        (transfer.accepted_event.tick, transfer.completed_event.tick,
         result.hit, result.target)
        for transfer, result in zip(transfers, results)
    ]
