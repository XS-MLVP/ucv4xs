"""One SC feedback beat updates separated resolved and predicted branch slots."""

from __future__ import annotations

import pytest

from bpuverify.sc.transaction.types import ScBaseBranch
from bpuverify.sc.transaction.types import ScBatchTraining
from bpuverify.sc.transaction.types import ScBranchFeedback
from bpuverify.sc.coverage.catalog import sc_batch_feedback_coverage_model
from bpuverify.sc.coverage.catalog import write_sc_batch_feedback_coverage
from bpuverify.sc.case.definitions import NOT_TAKEN_ATTEMPTS
from bpuverify.sc.case.definitions import PC
from bpuverify.sc.case.definitions import POSITION
from bpuverify.sc.case.definitions import TAGE_COUNTER
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-SC-013")
async def test_two_resolved_branches_train_distinct_prediction_slots(sc_agent):
    coverage = sc_batch_feedback_coverage_model()
    await sc_agent.reset()

    # Sc.getWayIdx XORs two-bit position chunks: positions 4 and 5 land in
    # different SC ways, so both updates must remain independently visible.
    later_position = POSITION + 1
    layout = (
        None,
        ScBaseBranch(POSITION, TAGE_COUNTER),
        None,
        ScBaseBranch(later_position, TAGE_COUNTER),
    )
    prediction = await sc_agent.predict_branches(PC, layout)
    assert prediction.useds[1] == prediction.useds[3] == 0
    assert prediction.meta["tagePredValid"][1] == 1
    assert prediction.meta["tagePredValid"][3] == 1

    feedback = (
        ScBranchFeedback(POSITION, 0, prediction_slot=1),
        None,
        ScBranchFeedback(later_position, 1, prediction_slot=3),
    )
    for _ in range(NOT_TAKEN_ATTEMPTS):
        await sc_agent.train_batch(ScBatchTraining(PC, prediction.meta, feedback))
        prediction = await sc_agent.predict_branches(PC, layout)
        if (
            (prediction.useds[1], prediction.takens[1]) == (1, 0)
            and (prediction.useds[3], prediction.takens[3]) == (1, 1)
        ):
            break
    else:
        raise AssertionError(f"simultaneous SC feedback did not converge: {prediction!r}")

    assert prediction.meta["useScPred"][1] == 1
    assert prediction.meta["useScPred"][3] == 1
    for resolved_slot, predicted_slot, direction in ((0, 1, 0), (2, 3, 1)):
        coverage.sample({
            "resolved_slot": resolved_slot,
            "predicted_slot": predicted_slot,
            "direction": direction,
        })
    coverage.assert_coverage(100.0)
    write_sc_batch_feedback_coverage(coverage, REPO_ROOT)
