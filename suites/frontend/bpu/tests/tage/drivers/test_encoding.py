from __future__ import annotations

import pytest

from bpuverify.tage.transaction.types import TageBaseBranch
from bpuverify.tage.transaction.types import TageBatchTraining
from bpuverify.tage.transaction.types import TageBranchFeedback
from bpuverify.tage.transaction.types import TageLookup
from bpuverify.tage.transaction.types import TageTraining


async def test_lookup_encoder_builds_main_btb_context(tage_agent):
    values = tage_agent.lookup_driver.encoder(TageLookup(0x4000_0000, 6, 1))
    assert values["start_pc"] == 0x4000_0000
    assert values["main_btb"]["s1_positions"][0] == 6
    result = tage_agent.base_driver.encoder(TageLookup(0x4000_0000, 6, 1))
    assert result["result"][0]["valid"] == 1
    assert result["result"][0]["bits"]["taken"] == 1
    assert result["result"][0]["bits"]["cfiPosition"] == 6


async def test_lookup_encoder_aligns_main_btb_context_with_previous_s0(tage_agent):
    first = TageLookup(0x4000_0000, 6, 1, 1)
    second = TageLookup(0x4000_0020, 7, 0)
    tage_agent.lookup_driver.encoder(first)
    values = tage_agent.lookup_driver.encoder(second)

    assert values["start_pc"] == second.pc
    assert values["main_btb"]["s1_positions"][0] == first.position
    base = tage_agent.base_driver.encoder(first)
    assert base["result"][0]["bits"]["cfiPosition"] == first.position
    assert base["result"][0]["bits"]["taken"] == first.base_taken
    assert base["baseConf"][0] == first.base_conf


async def test_lookup_encoder_preserves_main_btb_vector_slots(tage_agent):
    branches = (TageBaseBranch(5, 0), None, TageBaseBranch(9, 1, 1))
    first = TageLookup(0x4000_0000, 5, 0, branches=branches)
    second = TageLookup(0x4000_0020, 6, 0)
    tage_agent.lookup_driver.encoder(first)
    positions = tage_agent.lookup_driver.encoder(second)["main_btb"]["s1_positions"]
    base = tage_agent.base_driver.encoder(first)
    assert (positions[0], positions[2]) == (5, 9)
    assert [entry["valid"] for entry in base["result"]] == [1, 0, 1, 0]
    assert base["baseConf"] == (0, 0, 1, 0)


@pytest.mark.parametrize("branches", [
    (),
    (None,),
    (TageBaseBranch(5, 0), TageBaseBranch(5, 1)),
    (TageBaseBranch(5, 0),) * 5,
])
async def test_lookup_rejects_invalid_main_btb_vectors(tage_agent, branches):
    with pytest.raises(ValueError):
        tage_agent.submit_predict_branches(0x4000_0000, branches)


async def test_training_encoder_preserves_saturated_base_counter(tage_agent):
    transaction = TageTraining(0x4000_0000, 6, 0, 0, {}, mispredict=0, base_counter_value=0)
    values = tage_agent.encode_training(transaction)
    assert values["mbtb_meta"][0][0]["counter_value"] == 0
    assert values["branches"][0]["mispredict"] == 0

    with pytest.raises(ValueError, match="match base_taken"):
        tage_agent.encode_training(
            TageTraining(0x4000_0000, 6, 0, 1, {}, base_counter_value=0)
        )


async def test_batch_encoder_maps_resolve_slots_through_mbtb_hits(tage_agent):
    first = TageBranchFeedback(6, 0, 1, {"tag": "first"})
    second = TageBranchFeedback(7, 1, 0, {"tag": "second"})
    values = tage_agent.encode_batch_training(
        TageBatchTraining(0x4000_0000, (first, None, second))
    )
    assert [entry["position"] for bank in values["mbtb_meta"] for entry in bank][:2] == [6, 7]
    assert [entry["rawHit"] for bank in values["mbtb_meta"] for entry in bank] == [1, 1, 0, 0]
    assert values["tage_meta"][:2] == ({"tag": "first"}, {"tag": "second"})
    assert [branch["valid"] for branch in values["branches"]][:3] == [1, 0, 1]

    with pytest.raises(ValueError, match="positions must be distinct"):
        tage_agent.encode_batch_training(
            TageBatchTraining(0x4000_0000, (first, first))
        )
    with pytest.raises(ValueError, match="at most one mispredicted"):
        tage_agent.encode_batch_training(
            TageBatchTraining(0x4000_0000, (
                TageBranchFeedback(6, 0, 1, {}, mispredict=1),
                TageBranchFeedback(7, 1, 0, {}, mispredict=1),
            ))
        )


async def test_batch_encoder_keeps_valid_mbtb_misses_unmatched(tage_agent):
    missed = TageBranchFeedback(6, 0, 1, {"tag": "miss"}, mbtb_hit=0)
    matched = TageBranchFeedback(7, 1, 1, {"tag": "hit"})
    values = tage_agent.encode_batch_training(
        TageBatchTraining(0x4000_0000, (missed, None, matched))
    )
    entries = [entry for bank in values["mbtb_meta"] for entry in bank]
    assert [entry["rawHit"] for entry in entries] == [1, 0, 0, 0]
    assert entries[0]["position"] == matched.position
    assert values["tage_meta"][0] == matched.meta
    assert [branch["valid"] for branch in values["branches"]][:3] == [1, 0, 1]

    only_miss = tage_agent.encode_batch_training(
        TageBatchTraining(0x4000_0000, (missed,))
    )
    assert all(
        entry["rawHit"] == 0
        for bank in only_miss["mbtb_meta"] for entry in bank
    )
