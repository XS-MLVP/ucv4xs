"""ITTAGE chooses the sole eligible branch from a real FTQ feedback vector."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ittage.transaction.types import IttageBatchTraining
from suites.frontend.bpu.ittage.transaction.types import IttageBranchFeedback
from suites.frontend.bpu.ittage.coverage.catalog import ittage_branch_vector_coverage_model
from suites.frontend.bpu.ittage.coverage.catalog import write_ittage_branch_vector_coverage
from suites.frontend.bpu.ittage.case.definitions import PC
from suites.frontend.bpu.ittage.case.definitions import TARGET_A
from suites.frontend.bpu.ittage.case.definitions import TARGET_B
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-ITTAGE-013")
async def test_earlier_valid_ineligible_branches_do_not_mask_later_indirect(ittage_agent):
    coverage = ittage_branch_vector_coverage_model()
    conditional_prefix = tuple(
        IttageBranchFeedback(
            position=1 + 2 * index,
            target=TARGET_B + index * 0x20,
            taken=0,
            branch_type=1,
        )
        for index in range(4)
    )

    await ittage_agent.reset()
    cold = await ittage_agent.predict(PC)
    assert cold.hit == 0 and cold.meta["allocate"]["valid"] == 1
    await ittage_agent.train_batch(
        IttageBatchTraining(
            PC,
            cold.meta,
            conditional_prefix
            + (IttageBranchFeedback(position=9, target=TARGET_A, taken=1, mispredict=1),),
        )
    )
    chosen = await ittage_agent.predict(PC)
    assert (chosen.hit, chosen.target) == (1, TARGET_A)
    coverage.sample({"selection": "four_prior_conditionals"})

    await ittage_agent.reset()
    cold = await ittage_agent.predict(PC)
    assert cold.hit == 0 and cold.meta["allocate"]["valid"] == 1
    await ittage_agent.train_batch(
        IttageBatchTraining(
            PC,
            cold.meta,
            (
                *conditional_prefix[:2],
                IttageBranchFeedback(
                    position=7, target=TARGET_A, taken=1, mispredict=1, ras_action=2
                ),
            ),
        )
    )
    chosen = await ittage_agent.predict(PC)
    assert (chosen.hit, chosen.target) == (1, TARGET_A)
    coverage.sample({"selection": "indirect_call_after_conditionals"})

    await ittage_agent.reset()
    cold = await ittage_agent.predict(PC)
    assert cold.hit == 0 and cold.meta["allocate"]["valid"] == 1
    await ittage_agent.train_batch(
        IttageBatchTraining(
            PC,
            cold.meta,
            conditional_prefix[:2]
            + (IttageBranchFeedback(
                position=5, target=TARGET_A, taken=1, mispredict=1, ras_action=1
            ),),
        )
    )
    still_cold = await ittage_agent.predict(PC)
    assert still_cold.hit == 0
    coverage.sample({"selection": "return_only_rejected"})

    await ittage_agent.train_batch(
        IttageBatchTraining(
            PC,
            still_cold.meta,
            (
                conditional_prefix[0],
                IttageBranchFeedback(position=7, target=TARGET_B, taken=1, mispredict=1),
            ),
        )
    )
    chosen = await ittage_agent.predict(PC)
    assert (chosen.hit, chosen.target) == (1, TARGET_B)
    coverage.sample({"selection": "valid_after_rejected"})

    coverage.assert_coverage(100.0)
    write_ittage_branch_vector_coverage(coverage, REPO_ROOT)
