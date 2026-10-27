"""MicroTAGE must keep all AheadBTB slots aligned across lookup and train."""

from __future__ import annotations

import pytest

from bpuverify.utage.transaction.types import UtageBaseBranch
from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.coverage.catalog import utage_vector_coverage_model
from bpuverify.utage.coverage.catalog import write_utage_vector_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.case.definitions import PASSING_PC
from bpuverify.utage.case.definitions import POSITION


@pytest.mark.feature("BPU-UTAGE-014")
async def test_late_ahead_btb_slots_and_overlapped_lookups(utage_agent):
    coverage = utage_vector_coverage_model()

    for slot in (1, 2, 3):
        await utage_agent.reset()
        late_position = POSITION + 2 * slot
        branches = [UtageBaseBranch(POSITION, 0)]
        branches.extend([None] * (slot - 1))
        branches.append(UtageBaseBranch(late_position, 0))

        cold = await utage_agent.predict_branches(PASSING_PC, branches)
        assert len(cold.hits) == len(cold.takens) == 4
        assert cold.hits[0] == cold.hits[slot] == 0
        metadata = cold.meta["abtbResult"]
        assert metadata[0]["valid"] == metadata[slot]["valid"] == 1
        assert metadata[0]["cfiPosition"] == POSITION
        assert metadata[slot]["cfiPosition"] == late_position
        assert metadata[slot]["baseTaken"] == 0
        assert all(metadata[index]["valid"] == 0 for index in range(4) if index not in (0, slot))

        # The earlier conditional falls through. Only the later conditional
        # disagrees with its not-taken base and should receive a correction.
        await utage_agent.train(UtageTraining(PASSING_PC, late_position, 1, cold.meta))
        corrected = await utage_agent.predict_branches(PASSING_PC, branches)
        assert corrected.hits[0] == 0, (slot, corrected)
        assert (corrected.hits[slot], corrected.takens[slot]) == (1, 1), (slot, corrected)
        assert corrected.meta["abtbResult"][slot]["hit"] == 1
        assert corrected.meta["abtbResult"][slot]["cfiPosition"] == late_position
        coverage.sample({"corrected_slot": slot, "association": "serial"})

    # Distinct vector layouts and path histories then share a running S0/A1/A2
    # pipeline. The scoreboard must associate every observed vector with its
    # own accepted lookup, not the latest AheadBTB input on the wires.
    await utage_agent.reset()
    trained_branches = (UtageBaseBranch(POSITION, 0), None, UtageBaseBranch(POSITION + 4, 0))
    cold_branches = (UtageBaseBranch(POSITION + 1, 0), None, None, UtageBaseBranch(POSITION + 6, 0))
    trained_cold = await utage_agent.predict_branches(PASSING_PC, trained_branches)
    await utage_agent.train(UtageTraining(PASSING_PC, POSITION + 4, 1, trained_cold.meta))

    layouts = ((trained_branches, 0, 2, 1), (cold_branches, 8, 3, 0)) * 2
    transfers = [
        utage_agent.submit_predict_branches(PASSING_PC, branches, folded_history=history)
        for branches, history, _, _ in layouts
    ]
    await utage_agent.drain_predictions()
    results = [await transfer for transfer in transfers]
    accepted_ticks = [transfer.accepted_event.tick for transfer in transfers]
    assert accepted_ticks == list(range(accepted_ticks[0], accepted_ticks[0] + 2 * len(transfers), 2))
    for index, (result, (branches, _, later_slot, expected_hit)) in enumerate(zip(results, layouts)):
        assert result.hits[0] == 0
        assert (result.hits[later_slot], result.takens[later_slot]) == (
            expected_hit, expected_hit,
        ), (branches, result)
        metadata = result.meta["abtbResult"]
        assert metadata[0]["cfiPosition"] == branches[0].position
        assert metadata[later_slot]["cfiPosition"] == branches[later_slot].position
        assert metadata[later_slot]["valid"] == 1, (
            index, accepted_ticks,
            [(entry["valid"], entry["baseTaken"], entry["cfiPosition"]) for entry in metadata],
            branches,
        )
    coverage.sample({"corrected_slot": 2, "association": "overlap"})

    coverage.assert_coverage(100.0)
    write_utage_vector_coverage(coverage, REPO_ROOT)
