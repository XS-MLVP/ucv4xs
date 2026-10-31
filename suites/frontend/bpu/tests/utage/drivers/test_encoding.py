"""MicroTAGE lookup encoder builds AheadBTB context."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.utage.agent.main import UtageAgent
from suites.frontend.bpu.utage.transaction.types import UtageBaseBranch
from suites.frontend.bpu.utage.transaction.types import UtageLookup
from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.models.configuration import PHR_STORAGE_BITS
from suites.frontend.bpu.models.folded_history import folded_history_values
from suites.frontend.bpu.models.folded_history import PHR_FOLD_LAYOUT


async def test_lookup_encoder_maps_position_and_base_direction(utage_agent):
    values = utage_agent.lookup_driver.encoder(UtageLookup(0x4000_0000, 5, 1))
    assert values["start_pc"] == 0x4000_0000
    assert values["ahead_btb"]["fastPositions"][0] == 5
    result = utage_agent.result_driver.encoder(UtageLookup(0x4000_0000, 5, 1))
    assert result[0]["valid"] == 1
    assert result[0]["bits"]["attribute_branchType"] == 1
    assert result[0]["bits"]["taken"] == 1
    # Whole-chip DCE exposes only the fold indices consumed by MicroTage:
    # normal history has two index folds, S1/override four tag folds each.
    assert values["normal_history"] == ({"foldedHist": 0},) * 2
    assert values["s1_history"] == ({"foldedHist": 0},) * 4
    assert values["override_history"] == ({"foldedHist": 0},) * 4


async def test_lookup_encoder_aligns_a1_context_with_previous_a0(utage_agent):
    first = UtageLookup(0x4000_0000, 5, 1, folded_history=0)
    second = UtageLookup(0x4000_0020, 6, 0, folded_history=0b1000)
    utage_agent.lookup_driver.encoder(first)
    values = utage_agent.lookup_driver.encoder(second)

    assert values["start_pc"] == second.pc
    assert values["normal_history"] == ({"foldedHist": 8},) * 2
    assert values["new_start_pc"] == first.pc
    assert values["s1_history"] == ({"foldedHist": 0},) * 4
    assert values["ahead_btb"]["fastPositions"][0] == first.position


async def test_lookup_encoder_folds_older_history_and_preserves_previous_a0(utage_agent):
    first = UtageLookup(0x4000_0000, 5, 1, folded_history=256 | 3)
    second = UtageLookup(0x4000_0000, 5, 0, folded_history=2048 | 1)
    utage_agent.lookup_driver.encoder(first)
    values = utage_agent.lookup_driver.encoder(second)
    normal = folded_history_values(2048 | 1, len(PHR_FOLD_LAYOUT))
    s1 = folded_history_values(256 | 3, len(PHR_FOLD_LAYOUT))
    assert values["normal_history"] == (
        {"foldedHist": normal[2]["foldedHist"]},
        {"foldedHist": normal[7]["foldedHist"]},
    )
    assert values["s1_history"] == (
        {"foldedHist": s1[1]["foldedHist"]},
        {"foldedHist": s1[2]["foldedHist"]},
        {"foldedHist": s1[5]["foldedHist"]},
        {"foldedHist": s1[6]["foldedHist"]},
    )
    assert values["override_history"] == tuple(
        {"foldedHist": normal[index]["foldedHist"]} for index in (1, 2, 5, 6))


async def test_lookup_rejects_invalid_history_before_submission(utage_agent):
    previous = utage_agent._last_a0_lookup
    tasks = len(utage_agent._result_tasks)
    with pytest.raises(ValueError):
        utage_agent.submit_predict(0x4000_0000, 5, 0, folded_history=1 << PHR_STORAGE_BITS)
    assert utage_agent._last_a0_lookup is previous
    assert len(utage_agent._result_tasks) == tasks


async def test_lookup_encoder_keeps_vector_slots_and_previous_a0_alignment(utage_agent):
    branches = (UtageBaseBranch(5, 0), None, UtageBaseBranch(9, 1))
    first = UtageLookup(0x4000_0000, 5, 0, branches=branches)
    second = UtageLookup(0x4000_0020, 6, 0)
    utage_agent.lookup_driver.encoder(first)
    values = utage_agent.lookup_driver.encoder(second)

    assert values["start_pc"] == second.pc
    assert values["new_start_pc"] == first.pc
    ahead = values["ahead_btb"]
    result = utage_agent.result_driver.encoder(first)
    assert len(result) == len(ahead["fastPositions"]) == 4
    assert ahead["fastPositions"][0] == 5
    assert ahead["fastPositions"][2] == 9
    assert [entry["valid"] for entry in result] == [1, 0, 1, 0]
    assert result[2]["bits"]["taken"] == 1


@pytest.mark.parametrize("branches", [
    (),
    (None,),
    (UtageBaseBranch(5, 0), UtageBaseBranch(5, 1)),
    (UtageBaseBranch(5, 0),) * 5,
])
async def test_lookup_rejects_invalid_ahead_btb_vectors(utage_agent, branches):
    with pytest.raises(ValueError):
        utage_agent.submit_predict_branches(0x4000_0000, branches)


def test_training_encoder_preserves_feedback_and_metadata_without_mutation():
    metadata = {"readIndex": (12, 12)}
    transaction = UtageTraining(0x4000_0000, 5, 0, metadata, mispredict=0, branch_type=3, ras_action=2)
    values = UtageAgent.encode_training(transaction)
    assert values["start_pc"] == transaction.pc
    assert values["meta"] is metadata
    assert values["branch"] == {
        "taken": 0, "position": 5, "branch_type": 3,
    }
    assert metadata == {"readIndex": (12, 12)}


async def test_training_burst_rejects_empty_input(utage_agent):
    with pytest.raises(ValueError, match="burst must not be empty"):
        await utage_agent.train_many(())
