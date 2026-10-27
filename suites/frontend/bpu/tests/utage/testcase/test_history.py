"""Folded-path history must distinguish repeated branch positions."""

from __future__ import annotations

import pytest

from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.checker.assertions import counter
from bpuverify.utage.case.definitions import PASSING_PC
from bpuverify.utage.case.definitions import POSITION
from bpuverify.utage.case.definitions import SATURATION_ATTEMPTS


@pytest.mark.feature("BPU-UTAGE-010")
async def test_same_pc_separates_folded_history_counter_state(utage_agent):
    await utage_agent.reset()
    pc, position = PASSING_PC, POSITION
    history_a, history_b = 0, 0b1000

    cold_a = await utage_agent.predict(pc, position, 0, folded_history=history_a)
    assert cold_a.hit == 0
    await utage_agent.train(UtageTraining(pc, position, 1, cold_a.meta))
    trained_a = await utage_agent.predict(pc, position, 0, folded_history=history_a)
    assert (trained_a.hit, trained_a.taken) == (1, 1)

    cold_b = await utage_agent.predict(pc, position, 0, folded_history=history_b)
    assert cold_b.hit == 0
    assert cold_b.meta["readIndex"] != trained_a.meta["readIndex"]
    await utage_agent.train(UtageTraining(pc, position, 1, cold_b.meta))
    trained_b = await utage_agent.predict(pc, position, 0, folded_history=history_b)
    assert (trained_b.hit, trained_b.taken) == (1, 1)

    for _ in range(SATURATION_ATTEMPTS):
        await utage_agent.train(UtageTraining(pc, position, 0, trained_b.meta))
        trained_b = await utage_agent.predict(pc, position, 1, folded_history=history_b)
    assert (trained_b.hit, trained_b.taken, counter(trained_b)) == (1, 0, 0)

    still_a = await utage_agent.predict(pc, position, 0, folded_history=history_a)
    assert (still_a.hit, still_a.taken) == (1, 1)

    # Submit overlapping predictions from both contexts; the scoreboard
    # aligns each monitor result with its accepted lookup.
    histories = (history_a, history_b, history_a, history_b)
    transfers = [
        utage_agent.submit_predict(pc, position, 0, folded_history=history)
        for history in histories
    ]
    await utage_agent.drain_predictions()
    results = [await transfer for transfer in transfers]
    assert [(result.hit, result.taken) for result in results] == [
        (1, 1), (1, 0), (1, 1), (1, 0)
    ], [
        (transfer.accepted_event.tick, transfer.completed_event.tick,
         result.hit, result.taken, result.meta["readIndex"])
        for transfer, result in zip(transfers, results)
    ]
