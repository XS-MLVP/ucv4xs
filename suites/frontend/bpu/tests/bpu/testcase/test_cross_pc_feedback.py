"""Adjacent FTQ feedback beats must retain their own MainBTB PC context."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.transaction.types import BpuTraining
from suites.frontend.bpu.bpu.coverage.catalog import bpu_cross_pc_feedback_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_cross_pc_feedback_coverage
from suites.frontend.bpu.bpu.checker.assertions import mbtb_counter_for_position
from suites.frontend.bpu.bpu.checker.assertions import mbtb_meta_for_position
from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect
from suites.frontend.bpu.bpu.case.definitions import EARLIER_TARGET
from suites.frontend.bpu.bpu.case.definitions import LATER_POSITION
from suites.frontend.bpu.bpu.case.definitions import PC
from suites.frontend.bpu.bpu.case.definitions import POSITION
from suites.frontend.bpu.bpu.case.definitions import REDIRECT_PC
from suites.frontend.bpu.runtime.paths import REPO_ROOT


SECOND_TARGET = REDIRECT_PC + 0x280


@pytest.mark.feature("BPU-INT-027")
async def test_adjacent_feedback_from_two_pcs_retains_context(bpu_agent):
    coverage = bpu_cross_pc_feedback_coverage_model()
    await bpu_agent.reset(PC)
    initial = await bpu_agent.next_transaction(start_pc=PC)
    await bpu_agent.configure_predictors(
        ubtb=False, abtb=False, tage=False, sc=False,
        ittage=False, ras=False, settle=True,
    )
    first_cold = await revisit_from_redirect(
        bpu_agent, PC, initial.meta.redirect
    )
    assert first_cold.prediction.taken == 0
    await bpu_agent.train(BpuTraining(
        PC, POSITION, EARLIER_TARGET, first_cold.meta.resolve,
        branch_type=1,
    ))

    second_cold = await revisit_from_redirect(
        bpu_agent, REDIRECT_PC, first_cold.meta.redirect
    )
    assert second_cold.prediction.taken == 0
    await bpu_agent.train(BpuTraining(
        REDIRECT_PC, LATER_POSITION, SECOND_TARGET,
        second_cold.meta.resolve, branch_type=1,
    ))

    first = await revisit_from_redirect(
        bpu_agent, PC, first_cold.meta.redirect
    )
    second = await revisit_from_redirect(
        bpu_agent, REDIRECT_PC, second_cold.meta.redirect
    )
    assert first.prediction.start_pc == PC
    assert second.prediction.start_pc == REDIRECT_PC
    assert mbtb_counter_for_position(first, POSITION) == 2
    assert mbtb_counter_for_position(second, LATER_POSITION) == 2
    coverage.sample({"phase": "two_pc_entries"})

    assert first.meta_tick == first.prediction_tick + 4
    assert second.meta_tick == second.prediction_tick + 4
    assert second.prediction_tick > first.prediction_tick
    assert mbtb_meta_for_position(first, POSITION)[1] != (
        mbtb_meta_for_position(second, LATER_POSITION)[1]
    )
    coverage.sample({"phase": "distinct_paired_metadata"})

    activity = await bpu_agent.train_batches_during_stream((
        BpuBatchTraining(
            PC, first.meta.resolve,
            (BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),),
        ),
        BpuBatchTraining(
            REDIRECT_PC, second.meta.resolve,
            (BpuBranchFeedback(
                LATER_POSITION, SECOND_TARGET, 1, taken=1,
            ),),
        ),
    ))
    # Two toffee edge ticks are one hardware cycle.
    accepted_ticks = activity.training_ticks
    assert accepted_ticks[1] == accepted_ticks[0] + 2, accepted_ticks
    coverage.sample({"phase": "adjacent_acceptance"})
    assert activity.prediction_ticks, activity
    assert all(
        accepted_ticks[0] <= tick <= accepted_ticks[-1]
        for tick in activity.prediction_ticks
    ), activity
    coverage.sample({"phase": "prediction_overlap"})

    first_after = await revisit_from_redirect(
        bpu_agent, PC, first_cold.meta.redirect
    )
    second_after = await revisit_from_redirect(
        bpu_agent, REDIRECT_PC, second_cold.meta.redirect
    )
    assert mbtb_counter_for_position(first_after, POSITION) == 1
    assert mbtb_counter_for_position(second_after, LATER_POSITION) == 3
    coverage.sample({"phase": "opposite_counter_updates"})

    coverage.assert_coverage(100.0)
    write_bpu_cross_pc_feedback_coverage(coverage, REPO_ROOT)
