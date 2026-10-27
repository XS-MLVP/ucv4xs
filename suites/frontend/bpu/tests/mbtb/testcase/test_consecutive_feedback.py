"""Consecutive FTQ feedback to one MainBTB physical set."""

from __future__ import annotations

import pytest

from bpuverify.mbtb.transaction.types import MbtbBatchTraining
from bpuverify.mbtb.transaction.types import MbtbBranchFeedback
from bpuverify.mbtb.coverage.catalog import mbtb_consecutive_feedback_coverage_model
from bpuverify.mbtb.coverage.catalog import write_mbtb_consecutive_feedback_coverage
from bpuverify.mbtb.checker.assertions import assert_miss
from bpuverify.mbtb.checker.assertions import assert_vector_hit
from bpuverify.mbtb.checker.assertions import matching_way
from bpuverify.mbtb.case.definitions import BranchVector
from bpuverify.mbtb.case.definitions import DIRECT
from bpuverify.mbtb.case.definitions import NUM_WAYS
from bpuverify.mbtb.case.definitions import SAME_PHYSICAL_SET_STRIDE
from bpuverify.common.env.paths import REPO_ROOT


def feedback(vector: BranchVector, metadata) -> MbtbBatchTraining:
    return MbtbBatchTraining(
        vector.pc,
        metadata,
        (
            MbtbBranchFeedback(
                vector.target,
                1,
                vector.position,
                vector.branch_type,
                mispredict=1,
            ),
        ),
    )


@pytest.mark.feature("BPU-MBTB-017")
async def test_consecutive_same_set_feedback_retains_both_entries(mbtb_agent):
    coverage = mbtb_consecutive_feedback_coverage_model()
    neighbor = BranchVector(
        DIRECT.pc + SAME_PHYSICAL_SET_STRIDE,
        DIRECT.target + 0x800,
        DIRECT.position,
        DIRECT.branch_type,
    )
    for order_name, vectors in (
        ("direct_first", (DIRECT, neighbor)),
        ("neighbor_first", (neighbor, DIRECT)),
    ):
        await mbtb_agent.reset()
        cold = [await mbtb_agent.predict(vector.pc) for vector in vectors]
        for prediction in cold:
            assert_miss(prediction)

        await mbtb_agent.train_burst(
            tuple(
                feedback(vector, prediction.meta_entries)
                for vector, prediction in zip(vectors, cold, strict=True)
            )
        )

        first = await mbtb_agent.predict(vectors[0].pc)
        second = await mbtb_agent.predict(vectors[1].pc)
        assert_vector_hit(first, vectors[0])
        assert_vector_hit(second, vectors[1])
        assert sum(entry.valid for entry in first.entries) == 1, first
        assert sum(entry.valid for entry in second.entries) == 1, second
        first_way = matching_way(first, vectors[0])
        second_way = matching_way(second, vectors[1])
        assert first_way != second_way, (first, second)
        assert first_way // NUM_WAYS == second_way // NUM_WAYS
        coverage.sample({"order": order_name})

    coverage.assert_coverage(100.0)
    write_mbtb_consecutive_feedback_coverage(coverage, REPO_ROOT)
