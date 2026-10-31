"""TAGE trains conditional branches, not direct or indirect jumps."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.tage.transaction.types import TageTraining
from suites.frontend.bpu.tage.coverage.catalog import tage_training_type_coverage_model
from suites.frontend.bpu.tage.coverage.catalog import write_tage_training_type_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.case.definitions import PC
from suites.frontend.bpu.tage.case.definitions import POSITION


@pytest.mark.feature("BPU-TAGE-016")
async def test_nonconditional_feedback_neither_allocates_nor_updates_provider(tage_agent):
    coverage = tage_training_type_coverage_model()
    await tage_agent.reset()

    for branch_type, label in ((2, "direct"), (3, "indirect")):
        branch_pc = PC + branch_type * 0x100
        cold = await tage_agent.predict(
            branch_pc, POSITION, 1, branch_type=branch_type
        )
        assert cold.meta["hasProvider"] == 0
        # Direction is correctly taken; mispredict=1 represents a bad target.
        await tage_agent.train(
            TageTraining(
                branch_pc, POSITION, 1, 1, cold.meta,
                mispredict=1, branch_type=branch_type,
            )
        )
        still_cold = await tage_agent.predict(
            branch_pc, POSITION, 1, branch_type=branch_type
        )
        assert still_cold.meta["hasProvider"] == 0, (label, still_cold)
        coverage.sample({"phase": f"{label}_cold_rejected"})

    await tage_agent.reset()
    cold = await tage_agent.predict(PC, POSITION, 0)
    assert cold.meta["hasProvider"] == 0
    await tage_agent.train(TageTraining(PC, POSITION, 1, 0, cold.meta))
    allocated = await tage_agent.predict(PC, POSITION, 0)
    assert allocated.meta["hasProvider"] == 1
    provider = (
        allocated.meta["providerTableIdx"],
        allocated.meta["providerWayIdx"],
        allocated.meta["providerTakenCtr_value"],
    )
    coverage.sample({"phase": "conditional_allocates"})

    for branch_type, label in ((2, "direct"), (3, "indirect")):
        nonconditional = await tage_agent.predict(
            PC, POSITION, 1, branch_type=branch_type
        )
        await tage_agent.train(
            TageTraining(
                PC, POSITION, 1, 1, nonconditional.meta,
                mispredict=1, branch_type=branch_type,
            )
        )
        retained = await tage_agent.predict(PC, POSITION, 0)
        assert retained.meta["hasProvider"] == 1
        assert (
            retained.meta["providerTableIdx"],
            retained.meta["providerWayIdx"],
            retained.meta["providerTakenCtr_value"],
        ) == provider, (label, retained)
        coverage.sample({"phase": f"{label}_provider_held"})

    # A correctly predicted conditional outcome still advances the provider
    # counter, proving the negative cases did not globally disable training.
    correct = await tage_agent.predict(PC, POSITION, 1)
    assert correct.meta["hasProvider"] == 1
    await tage_agent.train(
        TageTraining(PC, POSITION, 1, 1, correct.meta, mispredict=0)
    )
    updated = await tage_agent.predict(PC, POSITION, 1)
    assert updated.meta["hasProvider"] == 1
    assert (
        updated.meta["providerTableIdx"],
        updated.meta["providerWayIdx"],
    ) == provider[:2]
    assert updated.meta["providerTakenCtr_value"] == provider[2] + 1
    coverage.sample({"phase": "conditional_update_works"})

    coverage.assert_coverage(100.0)
    write_tage_training_type_coverage(coverage, REPO_ROOT)
