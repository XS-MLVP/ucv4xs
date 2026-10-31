"""Integrated FTQ feedback must reach both MainBTB branch counters."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.transaction.types import BpuTraining
from suites.frontend.bpu.bpu.coverage.catalog import bpu_batch_feedback_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_batch_feedback_coverage
from suites.frontend.bpu.bpu.checker.assertions import mbtb_counter_for_position
from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect
from suites.frontend.bpu.bpu.case.definitions import EARLIER_TARGET
from suites.frontend.bpu.bpu.case.definitions import LATER_POSITION
from suites.frontend.bpu.bpu.case.definitions import LATER_TARGET
from suites.frontend.bpu.bpu.case.definitions import PC
from suites.frontend.bpu.bpu.case.definitions import POSITION
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-INT-020")
async def test_integrated_multi_branch_feedback_updates_two_counters(bpu_agent):
    coverage = bpu_batch_feedback_coverage_model()
    await bpu_agent.reset(PC)
    initial = await bpu_agent.next_transaction(start_pc=PC)
    assert initial.prediction.taken == 0
    await bpu_agent.configure_predictors(
        ubtb=False, abtb=False, tage=False, sc=False,
        ittage=False, ras=False, settle=True,
    )
    cold = await revisit_from_redirect(bpu_agent, PC, initial.meta.redirect)
    assert cold.prediction.taken == 0

    await bpu_agent.train(
        BpuTraining(
            PC, POSITION, EARLIER_TARGET, cold.meta.resolve,
            branch_type=1,
        )
    )
    current = await revisit_from_redirect(bpu_agent, PC, cold.meta.redirect)
    assert mbtb_counter_for_position(current, POSITION) == 2
    coverage.sample({"phase": "first_resident"})

    # Earlier conditional falls through; later conditional is the sole
    # misprediction. Resolved slot 1 is deliberately left invalid.
    branches = (
        BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),
        None,
        BpuBranchFeedback(
            LATER_POSITION, LATER_TARGET, 1, taken=1, mispredict=1,
        ),
    )
    await bpu_agent.train_batch(BpuBatchTraining(PC, current.meta.resolve, branches))
    current = await revisit_from_redirect(bpu_agent, PC, cold.meta.redirect)
    assert (
        mbtb_counter_for_position(current, POSITION),
        mbtb_counter_for_position(current, LATER_POSITION),
    ) == (1, 2)
    _, repaired = await bpu_agent.next_prediction(
        start_pc=PC, target=LATER_TARGET, stage="s2",
        after_tick=current.prediction_tick,
    )
    assert (repaired.taken, repaired.position) == (1, LATER_POSITION)
    coverage.sample({"phase": "late_allocation_and_early_decrement"})

    # With both branches resident, a correctly predicted FTQ beat must
    # update both counters even though no branch has mispredict=1.
    correct = (
        BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),
        None,
        BpuBranchFeedback(LATER_POSITION, LATER_TARGET, 1, taken=1),
    )
    await bpu_agent.train_batch(BpuBatchTraining(PC, current.meta.resolve, correct))
    current = await revisit_from_redirect(bpu_agent, PC, cold.meta.redirect)
    assert (
        mbtb_counter_for_position(current, POSITION),
        mbtb_counter_for_position(current, LATER_POSITION),
    ) == (0, 3)
    coverage.sample({"phase": "both_correct_updates"})

    coverage.assert_coverage(100.0)
    write_bpu_batch_feedback_coverage(coverage, REPO_ROOT)
