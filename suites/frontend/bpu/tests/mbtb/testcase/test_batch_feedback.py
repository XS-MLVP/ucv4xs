"""One FTQ feedback beat can update two MainBTB conditional counters."""

from __future__ import annotations

import pytest

from bpuverify.mbtb.transaction.types import MbtbBatchTraining
from bpuverify.mbtb.transaction.types import MbtbBranchFeedback
from bpuverify.mbtb.coverage.catalog import mbtb_batch_feedback_coverage_model
from bpuverify.mbtb.coverage.catalog import write_mbtb_batch_feedback_coverage
from bpuverify.mbtb.checker.assertions import assert_miss
from bpuverify.mbtb.checker.assertions import assert_resident_pair
from bpuverify.mbtb.checker.assertions import matching_way
from bpuverify.mbtb.checker.assertions import train
from bpuverify.mbtb.case.definitions import BranchVector
from bpuverify.mbtb.case.definitions import CONDITIONAL
from bpuverify.mbtb.case.definitions import NUM_WAYS
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-MBTB-016")
async def test_two_conditional_counters_update_in_one_feedback_beat(mbtb_agent):
    coverage = mbtb_batch_feedback_coverage_model()
    await mbtb_agent.reset()
    earlier = CONDITIONAL
    later = BranchVector(earlier.pc, earlier.target + 0x600, 2, 1)
    cold = await mbtb_agent.predict(earlier.pc)
    assert_miss(cold)
    await train(mbtb_agent, earlier, cold.meta_entries)
    one = await mbtb_agent.predict(earlier.pc)
    await train(mbtb_agent, later, one.meta_entries)
    current = await mbtb_agent.predict(earlier.pc)
    ways = (matching_way(current, earlier), matching_way(current, later))
    assert ways[0] != ways[1]
    assert ways[0] // NUM_WAYS == ways[1] // NUM_WAYS
    assert_resident_pair(current, earlier, later, ways, 2)
    coverage.sample({"phase": "two_residents"})

    # The earlier branch must fall through for the later branch to execute.
    await train(mbtb_agent, earlier, current.meta_entries, taken=0)
    current = await mbtb_agent.predict(earlier.pc)
    assert_resident_pair(current, earlier, later, ways, 1)
    coverage.sample({"phase": "prepared"})

    # The earlier not-taken branch was predicted correctly; the later
    # not-taken branch is the sole misprediction in this FTQ feedback vector.
    await mbtb_agent.train_batch(
        MbtbBatchTraining(
            earlier.pc,
            current.meta_entries,
            (
                MbtbBranchFeedback(earlier.target, 0, earlier.position, 1),
                MbtbBranchFeedback(later.target, 0, later.position, 1, mispredict=1),
            ),
        )
    )
    current = await mbtb_agent.predict(earlier.pc)
    assert_resident_pair(current, earlier, later, ways, 0, neighbor_counter=1)
    coverage.sample({"phase": "slot_one_mispredict"})

    # Rebalance with one branch per beat: a taken misprediction at the earlier
    # branch masks the later branch, then the later counter becomes weak taken.
    await train(mbtb_agent, earlier, current.meta_entries, taken=1)
    current = await mbtb_agent.predict(earlier.pc)
    assert_resident_pair(current, earlier, later, ways, 1, neighbor_counter=1)
    await train(mbtb_agent, later, current.meta_entries, taken=1)
    current = await mbtb_agent.predict(earlier.pc)
    assert_resident_pair(current, earlier, later, ways, 1, neighbor_counter=2)
    coverage.sample({"phase": "rebalanced"})

    # Both outcomes now agree with prediction. No mispredictBranch is selected,
    # yet counters 1→0 and 2→3 must update together in this one beat.
    correct_feedback = MbtbBatchTraining(
        earlier.pc,
        current.meta_entries,
        (
            MbtbBranchFeedback(earlier.target, 0, earlier.position, 1),
            MbtbBranchFeedback(later.target, 1, later.position, 1),
        ),
    )
    await mbtb_agent.train_batch(correct_feedback)
    current = await mbtb_agent.predict(earlier.pc)
    assert_resident_pair(current, earlier, later, ways, 0, neighbor_counter=3)
    coverage.sample({"phase": "both_correct"})

    await mbtb_agent.train_batch(
        MbtbBatchTraining(earlier.pc, current.meta_entries, correct_feedback.branches)
    )
    saturated = await mbtb_agent.predict(earlier.pc)
    assert_resident_pair(saturated, earlier, later, ways, 0, neighbor_counter=3)
    coverage.sample({"phase": "saturated"})

    coverage.assert_coverage(100.0)
    write_mbtb_batch_feedback_coverage(coverage, REPO_ROOT)
