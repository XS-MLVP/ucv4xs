"""Correctly predicted feedback still updates a MainBTB conditional counter."""

from __future__ import annotations

import pytest

from bpuverify.mbtb.coverage.catalog import mbtb_correct_feedback_coverage_model
from bpuverify.mbtb.coverage.catalog import write_mbtb_correct_feedback_coverage
from bpuverify.mbtb.checker.assertions import assert_miss
from bpuverify.mbtb.checker.assertions import assert_resident_pair
from bpuverify.mbtb.checker.assertions import matching_entry
from bpuverify.mbtb.checker.assertions import matching_way
from bpuverify.mbtb.checker.assertions import train
from bpuverify.mbtb.case.definitions import BranchVector
from bpuverify.mbtb.case.definitions import CONDITIONAL
from bpuverify.mbtb.case.definitions import NUM_WAYS
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-MBTB-015")
async def test_correct_feedback_trains_counter_without_mispredict(mbtb_agent):
    coverage = mbtb_correct_feedback_coverage_model()
    await mbtb_agent.reset()
    neighbor = BranchVector(CONDITIONAL.pc, CONDITIONAL.target + 0x600, 2, 2)
    cold = await mbtb_agent.predict(CONDITIONAL.pc)
    assert_miss(cold)
    await train(mbtb_agent, CONDITIONAL, cold.meta_entries)
    single = await mbtb_agent.predict(CONDITIONAL.pc)
    await train(mbtb_agent, neighbor, single.meta_entries)
    current = await mbtb_agent.predict(CONDITIONAL.pc)
    ways = (matching_way(current, CONDITIONAL), matching_way(current, neighbor))
    assert ways[0] != ways[1]
    assert ways[0] // NUM_WAYS == ways[1] // NUM_WAYS
    assert_resident_pair(current, CONDITIONAL, neighbor, ways, 2)
    coverage.sample({"phase": "initial_weak_positive"})

    # Taken is currently predicted, so mispredict=0 is a consistent feedback.
    await train(
        mbtb_agent, CONDITIONAL, current.meta_entries, taken=1, mispredict=0
    )
    current = await mbtb_agent.predict(CONDITIONAL.pc)
    assert_resident_pair(current, CONDITIONAL, neighbor, ways, 3)
    coverage.sample({"phase": "correct_taken_saturates"})

    # Both not-taken outcomes contradict the current taken prediction.
    for expected_counter in (2, 1):
        assert matching_entry(current, CONDITIONAL).taken == 1
        await train(
            mbtb_agent, CONDITIONAL, current.meta_entries,
            taken=0, mispredict=1,
        )
        current = await mbtb_agent.predict(CONDITIONAL.pc)
        assert_resident_pair(current, CONDITIONAL, neighbor, ways, expected_counter)
    coverage.sample({"phase": "mispredict_crosses_negative"})

    # Prediction is now not-taken, and correct feedback must still reach the
    # counter update path even though there is no mispredict branch to write.
    for expected_counter, phase in (
        (0, "correct_not_taken_ages"),
        (0, "correct_not_taken_saturates"),
    ):
        assert matching_entry(current, CONDITIONAL).taken == 0
        await train(
            mbtb_agent, CONDITIONAL, current.meta_entries,
            taken=0, mispredict=0,
        )
        current = await mbtb_agent.predict(CONDITIONAL.pc)
        assert_resident_pair(current, CONDITIONAL, neighbor, ways, expected_counter)
        coverage.sample({"phase": phase})

    coverage.assert_coverage(100.0)
    write_mbtb_correct_feedback_coverage(coverage, REPO_ROOT)
