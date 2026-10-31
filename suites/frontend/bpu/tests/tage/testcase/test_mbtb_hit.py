"""TAGE training requires a matching MainBTB metadata entry."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.tage.transaction.types import TageBatchTraining
from suites.frontend.bpu.tage.transaction.types import TageBranchFeedback
from suites.frontend.bpu.tage.transaction.types import TageTraining
from suites.frontend.bpu.tage.coverage.catalog import tage_mbtb_hit_coverage_model
from suites.frontend.bpu.tage.coverage.catalog import write_tage_mbtb_hit_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.case.definitions import PC
from suites.frontend.bpu.tage.case.definitions import POSITION


@pytest.mark.feature("BPU-TAGE-018")
async def test_mbtb_miss_blocks_training_without_masking_a_later_hit(tage_agent):
    coverage = tage_mbtb_hit_coverage_model()
    await tage_agent.reset()

    cold = await tage_agent.predict(PC, POSITION, 0)
    assert cold.meta["hasProvider"] == 0
    await tage_agent.train(
        TageTraining(PC, POSITION, 1, 0, cold.meta, mbtb_hit=0)
    )
    still_cold = await tage_agent.predict(PC, POSITION, 0)
    assert still_cold.meta["hasProvider"] == 0
    coverage.sample({"phase": "cold_miss_rejected"})

    # The same resolved branch and prediction metadata may train once a real
    # MainBTB hit is present in the FTQ metadata.
    await tage_agent.train(
        TageTraining(PC, POSITION, 1, 0, still_cold.meta, mbtb_hit=1)
    )
    resident = await tage_agent.predict(PC, POSITION, 1)
    assert resident.meta["hasProvider"] == 1
    assert resident.meta["providerTakenCtr_value"] == 4
    cell = (resident.meta["providerTableIdx"], resident.meta["providerWayIdx"])
    coverage.sample({"phase": "matched_allocates"})

    # Even an already resident provider must ignore feedback whose MainBTB
    # prediction metadata has no matching rawHit/position entry.
    await tage_agent.train(
        TageTraining(
            PC, POSITION, 1, 1, resident.meta,
            mispredict=0, mbtb_hit=0,
        )
    )
    held = await tage_agent.predict(PC, POSITION, 1)
    assert (
        held.meta["providerTableIdx"],
        held.meta["providerWayIdx"],
        held.meta["providerTakenCtr_value"],
    ) == (*cell, 4)
    coverage.sample({"phase": "resident_miss_held"})

    # A missed earlier conditional branch falls through. Its absence from
    # MainBTB metadata must not prevent a later matched branch in the same
    # feedback beat from updating its own provider.
    other_position = POSITION + 2
    other = await tage_agent.predict(PC, other_position, 1)
    assert other.meta["hasProvider"] == 0
    await tage_agent.train_batch(
        TageBatchTraining(
            PC,
            (
                TageBranchFeedback(
                    other_position, 0, 1, other.meta,
                    mispredict=1, mbtb_hit=0,
                ),
                None,
                TageBranchFeedback(
                    POSITION, 1, 1, held.meta,
                    mispredict=0, mbtb_hit=1,
                ),
            ),
        )
    )
    other_after = await tage_agent.predict(PC, other_position, 1)
    updated = await tage_agent.predict(PC, POSITION, 1)
    assert other_after.meta["hasProvider"] == 0
    assert (
        updated.meta["providerTableIdx"],
        updated.meta["providerWayIdx"],
        updated.meta["providerTakenCtr_value"],
    ) == (*cell, 5)
    coverage.sample({"phase": "mixed_vector_hit_only"})

    coverage.assert_coverage(100.0)
    write_tage_mbtb_hit_coverage(coverage, REPO_ROOT)
