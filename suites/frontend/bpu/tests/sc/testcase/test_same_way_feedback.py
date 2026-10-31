"""Opposite outcomes to one SC way cancel within a single feedback beat."""

from __future__ import annotations
from suites.frontend.bpu.models.configuration import *

import pytest

from suites.frontend.bpu.sc.transaction.types import ScBaseBranch
from suites.frontend.bpu.sc.transaction.types import ScBatchTraining
from suites.frontend.bpu.sc.transaction.types import ScBranchFeedback
from suites.frontend.bpu.sc.coverage.catalog import sc_same_way_feedback_coverage_model
from suites.frontend.bpu.sc.coverage.catalog import write_sc_same_way_feedback_coverage
from suites.frontend.bpu.sc.checker.assertions import learn
from suites.frontend.bpu.sc.case.definitions import NOT_TAKEN_ATTEMPTS
from suites.frontend.bpu.sc.case.definitions import PC
from suites.frontend.bpu.sc.case.definitions import TAGE_COUNTER
from suites.frontend.bpu.runtime.paths import REPO_ROOT


EARLIER_POSITION = 1
LATER_POSITION = 8


@pytest.mark.feature("BPU-SC-014")
async def test_opposite_branch_feedback_cancels_in_one_sc_way(sc_agent):
    coverage = sc_same_way_feedback_coverage_model()
    await sc_agent.reset()
    layout = (
        ScBaseBranch(EARLIER_POSITION, TAGE_COUNTER),
        ScBaseBranch(LATER_POSITION, TAGE_COUNTER),
    )
    initial = await sc_agent.predict_branches(PC, layout)
    assert initial.useds[:2] == (0, 0)
    assert initial.meta["tagePredValid"][:2] == (1, 1)
    assert initial.meta["sumAboveThres"][:2] == (0, 0)
    assert initial.meta["scBiasLowerBits"][0] == initial.meta["scBiasLowerBits"][1]
    assert initial.meta["scPred"][0] == initial.meta["scPred"][1]
    coverage.sample({"phase": "both_qualified"})

    feedback = (
        ScBranchFeedback(EARLIER_POSITION, 0, prediction_slot=0),
        ScBranchFeedback(LATER_POSITION, 1, prediction_slot=1),
    )
    prediction = initial
    for _ in range(NOT_TAKEN_ATTEMPTS):
        await sc_agent.train_batch(ScBatchTraining(PC, prediction.meta, feedback))
        prediction = await sc_agent.predict_branches(PC, layout)
        assert prediction.useds[:2] == (0, 0), prediction
        assert prediction.meta["scPred"][:2] == initial.meta["scPred"][:2]
    coverage.sample({"phase": "opposite_cancelled"})

    # The same physical way must still be trainable. A slot-zero-only driver
    # would already have learned not-taken during the cancellation loop.
    learned = await learn(sc_agent, 0, pc=PC, position=EARLIER_POSITION)
    assert (learned.used, learned.taken) == (1, 0)
    aliased = await sc_agent.predict_branches(PC, layout)
    assert aliased.useds[:2] == (1, 1)
    assert aliased.takens[:2] == (0, 0)
    coverage.sample({"phase": "single_branch_control"})
    coverage.sample({"phase": "both_slots_alias"})

    coverage.assert_coverage(100.0)
    write_sc_same_way_feedback_coverage(coverage, REPO_ROOT)
