from __future__ import annotations

import pytest

from bpuverify.ittage.transaction.types import IttageBatchTraining
from bpuverify.ittage.transaction.types import IttageBranchFeedback
from bpuverify.ittage.transaction.types import IttageLookup


@pytest.mark.feature("ENV-IF-001")
async def test_batch_encoder_prunes_pc_targets_and_metadata_without_mutation(ittage_agent):
    meta = {"providerTarget_addr": 0x4010_0120, "altProviderTarget_addr": 0x4000_0120}
    transaction = IttageBatchTraining(
        0x400F_FF00, meta,
        (IttageBranchFeedback(position=7, target=0x4010_0120, taken=1, mispredict=1),),
    )
    values = ittage_agent._encode_batch_training(transaction)
    assert values["start_pc"] == 0x2007_FF80
    assert values["branches"][0]["target"] == 0x2008_0090
    assert values["meta"] == {"providerTarget_addr": 0x2008_0090, "altProviderTarget_addr": 0x2000_0090}
    assert meta == {"providerTarget_addr": 0x4010_0120, "altProviderTarget_addr": 0x4000_0120}


@pytest.mark.feature("ENV-IF-001")
async def test_bad_later_burst_address_does_not_partially_drive_feedback(ittage_agent, monkeypatch):
    sent = []
    original = ittage_agent.training_driver.send_many

    async def send_many(transactions):
        sent.append(transactions)
        return await original(transactions)

    monkeypatch.setattr(ittage_agent.training_driver, "send_many", send_many)
    good = IttageBatchTraining(0x4000_0000, {}, (IttageBranchFeedback(7, 0x4000_1234, 1),))
    bad = IttageBatchTraining(0x4000_0020, {}, (IttageBranchFeedback(7, 0x4000_1235, 1),))
    with pytest.raises(ValueError, match="halfword-aligned byte address"):
        await ittage_agent.train_batches((good, bad))
    assert sent == []


async def test_lookup_encoder_maps_all_fire_controls(ittage_agent):
    values = ittage_agent.lookup_driver.encoder(IttageLookup(0x4000_0000, 0))
    assert values == {
        "s0_fire": 1,
        "s1_fire": 1,
        "s2_fire": 1,
        "s3_fire": 1,
        "start_pc": 0x2000_0000,
        "folded_history": ({"foldedHist": 0},) * 19,
    }


async def test_lookup_encoder_aligns_s1_history_with_previous_s0(ittage_agent):
    first = IttageLookup(0x4000_0000, folded_history=0)
    second = IttageLookup(0x4000_0020, folded_history=0b0100)
    ittage_agent.lookup_driver.encoder(first)
    values = ittage_agent.lookup_driver.encoder(second)

    assert values["start_pc"] == second.pc >> 1
    assert values["folded_history"] == ({"foldedHist": 0},) * 19
    third = ittage_agent.lookup_driver.encoder(first)
    assert third["folded_history"] == ({"foldedHist": 4},) * 19


async def test_batch_training_rejects_two_ittage_candidates(ittage_agent):
    feedback = IttageBatchTraining(
        0x4000_0000,
        {},
        (
            IttageBranchFeedback(position=1, target=0x4000_1000, taken=1),
            IttageBranchFeedback(position=3, target=0x4000_2000, taken=1),
        ),
    )
    with pytest.raises(ValueError, match="qualifying branch"):
        await ittage_agent.train_batch(feedback)


async def test_batch_training_rejects_two_mispredictions(ittage_agent):
    feedback = IttageBatchTraining(
        0x4000_0000,
        {},
        (
            IttageBranchFeedback(position=1, target=0x4000_1000, taken=0, mispredict=1),
            IttageBranchFeedback(position=3, target=0x4000_2000, taken=1, mispredict=1),
        ),
    )
    with pytest.raises(ValueError, match="mispredicted branch"):
        await ittage_agent.train_batch(feedback)
