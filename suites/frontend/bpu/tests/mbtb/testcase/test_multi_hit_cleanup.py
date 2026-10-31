"""Real stale FTQ metadata can expose and clean MainBTB duplicate ways."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.mbtb.case.retained_pressure import preceding_displacers
from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining
from suites.frontend.bpu.mbtb.transaction.types import MbtbBranchFeedback
from suites.frontend.bpu.mbtb.coverage.catalog import mbtb_multi_hit_cleanup_coverage_model
from suites.frontend.bpu.mbtb.coverage.catalog import write_mbtb_multi_hit_cleanup_coverage
from suites.frontend.bpu.mbtb.checker.assertions import assert_miss
from suites.frontend.bpu.mbtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.mbtb.checker.assertions import matching_way
from suites.frontend.bpu.mbtb.checker.assertions import train
from suites.frontend.bpu.mbtb.case.definitions import BranchVector
from suites.frontend.bpu.mbtb.case.definitions import DIRECT
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-MBTB-019")
async def test_stale_feedback_duplicate_is_flushed_without_touching_other_set(mbtb_agent):
    coverage = mbtb_multi_hit_cleanup_coverage_model()
    await mbtb_agent.reset()
    cold = await mbtb_agent.predict(DIRECT.pc)
    assert_miss(cold)
    shadow_displacer = BranchVector(
        DIRECT.pc + 128,
        DIRECT.target + 0x1020,
        DIRECT.position,
        DIRECT.branch_type,
    )
    displacer_cold = await mbtb_agent.predict(shadow_displacer.pc)
    assert_miss(displacer_cold)

    def feedback(target: int) -> MbtbBatchTraining:
        return MbtbBatchTraining(
            DIRECT.pc,
            cold.meta_entries,
            (
                MbtbBranchFeedback(
                    target,
                    1,
                    DIRECT.position,
                    DIRECT.branch_type,
                    mispredict=1,
                ),
            ),
        )

    changed_target = DIRECT.target + 0x400
    async with mbtb_agent.defer_multi_hit_cleanup():
        await mbtb_agent.train_burst((feedback(DIRECT.target),))
        await preceding_displacers(mbtb_agent, shadow_displacer.pc, shadow_displacer.position,
                                   shadow_displacer.target, shadow_displacer.branch_type)
        await train(mbtb_agent, shadow_displacer, displacer_cold.meta_entries)
        first = await mbtb_agent.predict(DIRECT.pc)
        assert_vector_hit(first, DIRECT)
        assert sum(entry.valid for entry in first.entries) == 1
        first_way = matching_way(first, DIRECT)
        other_before = await mbtb_agent.predict(shadow_displacer.pc)
        assert_vector_hit(other_before, shadow_displacer)
        assert sum(entry.valid for entry in other_before.entries) == 1
        other_way = matching_way(other_before, shadow_displacer)
        coverage.sample({"phase": "resident_after_other_set"})
        await mbtb_agent.train_burst((feedback(changed_target),))
        observed = await mbtb_agent.predict(DIRECT.pc)
        duplicate = [
            (way, entry.target)
            for way, entry in enumerate(observed.entries)
            if entry.valid and entry.position == DIRECT.position
        ]
        assert len(duplicate) == 2, (
            f"expected two public same-position hits, got {duplicate}; "
            f"metadata={observed.meta_entries!r}"
        )
        assert {target for _, target in duplicate} == {DIRECT.target, changed_target}
        assert next(way for way, target in duplicate if target == DIRECT.target) == first_way
        assert sum(entry.valid for entry in observed.entries) == 2
        assert sum(
            item["rawHit"] and item["position"] == DIRECT.position
            for bank in observed.meta_entries
            for item in bank
        ) == 2
        survivor_way, survivor_target = min(duplicate)
        coverage.sample({"phase": "public_double_hit"})

    cleaned = await mbtb_agent.predict(DIRECT.pc)
    cleaned_hits = [
        (way, entry.target)
        for way, entry in enumerate(cleaned.entries)
        if entry.valid and entry.position == DIRECT.position
    ]
    assert cleaned_hits == [(survivor_way, survivor_target)], cleaned
    assert sum(entry.valid for entry in cleaned.entries) == 1
    assert sum(
        item["rawHit"] and item["position"] == DIRECT.position
        for bank in cleaned.meta_entries
        for item in bank
    ) == 1
    coverage.sample({"phase": "single_survivor"})
    other_after = await mbtb_agent.predict(shadow_displacer.pc)
    assert_vector_hit(other_after, shadow_displacer)
    assert sum(entry.valid for entry in other_after.entries) == 1
    assert matching_way(other_after, shadow_displacer) == other_way
    coverage.sample({"phase": "other_set_preserved"})
    coverage.assert_coverage(100.0)
    write_mbtb_multi_hit_cleanup_coverage(coverage, REPO_ROOT)
