"""A lookup of MicroBTB's write-cycle victim must not return stale payload."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ubtb.transaction.types import BranchTraining
from suites.frontend.bpu.ubtb.coverage.catalog import ubtb_replacement_collision_coverage_model
from suites.frontend.bpu.ubtb.coverage.catalog import write_ubtb_replacement_collision_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.ubtb.checker.assertions import assert_hit
from suites.frontend.bpu.ubtb.checker.assertions import assert_miss
from suites.frontend.bpu.ubtb.checker.assertions import expected_prediction
from suites.frontend.bpu.ubtb.checker.assertions import train_taken
from suites.frontend.bpu.ubtb.case.definitions import NUM_ENTRIES
from suites.frontend.bpu.ubtb.case.definitions import capacity_vectors
from suites.frontend.bpu.ubtb.case.replacement import expected_victim


async def fill_and_touch_full_set(agent, residents):
    await agent.reset()
    for vector in residents:
        await train_taken(agent, vector)
    for vector in residents:
        await assert_hit(agent, vector)


@pytest.mark.feature("BPU-UBTB-015")
async def test_lookup_of_replacement_victim_is_suppressed_only_for_victim(ubtb_agent):
    coverage = ubtb_replacement_collision_coverage_model()
    vectors = capacity_vectors()
    assert len(vectors) == NUM_ENTRIES + 1
    residents, replacement = vectors[:NUM_ENTRIES], vectors[-1]
    update = BranchTraining(
        replacement.pc, replacement.target, 1,
        replacement.position, replacement.branch_type,
    )

    # The independent model predicts the victim before any DUT eviction is
    # observed. Replay the same event history for the two collision consumers.
    await fill_and_touch_full_set(ubtb_agent, residents)
    victim = expected_victim(ubtb_agent, residents)
    await train_taken(ubtb_agent, replacement)
    await assert_miss(ubtb_agent, victim.pc)
    for vector in residents:
        if vector != victim:
            await assert_hit(ubtb_agent, vector)
    survivor = next(vector for vector in residents if vector != victim)
    await assert_hit(ubtb_agent, replacement)
    coverage.sample({"phase": "calibrated_victim"})

    await fill_and_touch_full_set(ubtb_agent, residents)
    collision = await ubtb_agent.predict_on_training_write(update, victim.pc)
    assert collision.valid == 0, (victim, collision)
    coverage.sample({"phase": "victim_collision_miss"})
    await assert_miss(ubtb_agent, victim.pc)
    await assert_hit(ubtb_agent, replacement)
    for vector in residents:
        if vector != victim:
            await assert_hit(ubtb_agent, vector)
    coverage.sample({"phase": "replacement_visible"})

    # Replaying once more with a nonvictim query excludes an implementation
    # that simply suppresses every lookup during an unrelated write.
    await fill_and_touch_full_set(ubtb_agent, residents)
    collision = await ubtb_agent.predict_on_training_write(update, survivor.pc)
    assert collision == expected_prediction(survivor), (survivor, collision)
    coverage.sample({"phase": "survivor_collision_hit"})
    await assert_miss(ubtb_agent, victim.pc)
    await assert_hit(ubtb_agent, replacement)

    coverage.assert_coverage(100.0)
    write_ubtb_replacement_collision_coverage(coverage, REPO_ROOT)
