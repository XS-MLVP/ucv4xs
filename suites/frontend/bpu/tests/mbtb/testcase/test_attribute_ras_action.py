"""The call/return hint bits are part of the branch attribute, not spare payload.

MainBTB stores one attribute word per branch. The branch type has been trained
many times, but the two RAS hint bits (call/return/return-and-call) were never
varied, so a defect that dropped them would have been invisible. These cases
make the hint bits observable in both the prediction and the raw metadata, and
verify that changing only the hint at a resident position rewrites that entry
in place instead of consuming a way.
"""

from __future__ import annotations

import pytest

from bpuverify.mbtb.checker.assertions import matching_entry
from bpuverify.mbtb.checker.assertions import matching_way
from bpuverify.mbtb.checker.assertions import train
from bpuverify.mbtb.case.definitions import BranchVector
from bpuverify.mbtb.case.definitions import CONDITIONAL
from bpuverify.mbtb.case.definitions import NUM_WAYS


# One branch per align-bank/way slot of a 32-byte fetch block, covering all
# four RAS hint encodings: none, push (call), pop (return), pop-and-push.
HINT_VECTORS = (
    BranchVector(CONDITIONAL.pc, 0x4000_1234, 1, 1, ras_action=0),
    BranchVector(CONDITIONAL.pc, 0x4000_2340, 5, 2, ras_action=2),
    BranchVector(CONDITIONAL.pc, 0x4000_3456, 9, 3, ras_action=1),
    BranchVector(CONDITIONAL.pc, 0x4000_4560, 13, 3, ras_action=3),
)


@pytest.mark.feature("BPU-MBTB-003")
async def test_ras_action_hint_round_trips_with_the_rest_of_the_attribute(mbtb_agent):
    await mbtb_agent.reset()
    prediction = await mbtb_agent.predict(CONDITIONAL.pc)
    for vector in HINT_VECTORS:
        await train(mbtb_agent, vector, prediction.meta_entries)
        prediction = await mbtb_agent.predict(vector.pc)

    assert sum(entry.valid for entry in prediction.entries) == len(HINT_VECTORS)
    for vector in HINT_VECTORS:
        entry = matching_entry(prediction, vector)
        assert (entry.target, entry.position, entry.branch_type, entry.ras_action) == (
            vector.target, vector.position, vector.branch_type, vector.ras_action
        ), (vector, entry)
        # The raw metadata carries the same complete attribute, so a consumer
        # that uses the hint instead of the decoded prediction sees it too.
        hits = [
            item
            for bank in prediction.meta_entries
            for item in bank
            if item["rawHit"] and item["position"] == vector.position
        ]
        assert len(hits) == 1, (vector, prediction)
        assert (hits[0]["attribute"]["branchType"], hits[0]["attribute"]["rasAction"]) == (
            vector.branch_type, vector.ras_action
        ), (vector, hits[0])


@pytest.mark.feature("BPU-MBTB-014")
async def test_changing_only_the_ras_hint_rewrites_the_resident_way(mbtb_agent):
    """A resident direct branch becomes a direct call at the same position.

    The branch type and position are unchanged; only rasAction differs. The
    RTL compares the full attribute word, so this is an in-place rewrite of
    the hit way: the entry count stays two, the neighbor keeps its way, and no
    third way is consumed. If the attribute comparison ignored the hint bits,
    the stored action would stay zero and this check would fail.
    """

    await mbtb_agent.reset()
    branch = BranchVector(CONDITIONAL.pc, 0x4000_1234, 1, 2, ras_action=0)
    neighbor = BranchVector(CONDITIONAL.pc, 0x4000_5678, 2, 1, ras_action=0)
    cold = await mbtb_agent.predict(CONDITIONAL.pc)
    await train(mbtb_agent, branch, cold.meta_entries)
    one = await mbtb_agent.predict(CONDITIONAL.pc)
    await train(mbtb_agent, neighbor, one.meta_entries)
    current = await mbtb_agent.predict(CONDITIONAL.pc)
    assert sum(entry.valid for entry in current.entries) == 2
    branch_way = matching_way(current, branch)
    neighbor_way = matching_way(current, neighbor)
    assert branch_way != neighbor_way
    assert branch_way // NUM_WAYS == neighbor_way // NUM_WAYS

    call = BranchVector(CONDITIONAL.pc, 0x4000_1234, 1, 2, ras_action=2)
    await train(mbtb_agent, call, current.meta_entries)
    rewritten = await mbtb_agent.predict(CONDITIONAL.pc)

    assert sum(entry.valid for entry in rewritten.entries) == 2
    assert matching_way(rewritten, call) == branch_way
    assert matching_way(rewritten, neighbor) == neighbor_way
    entry = matching_entry(rewritten, call)
    assert (entry.branch_type, entry.ras_action) == (2, 2)
    assert entry.target == call.target
    # Re-initializing the overridden entry restores the weak-positive counter.
    assert entry.taken == 1
    neighbor_entry = matching_entry(rewritten, neighbor)
    assert (neighbor_entry.branch_type, neighbor_entry.ras_action) == (1, 0)
    assert neighbor_entry.target == neighbor.target
