"""Two same-way resolved branches advance SC learning in one feedback beat."""

from __future__ import annotations

import pytest

from bpuverify.sc.transaction.types import ScBaseBranch
from bpuverify.sc.transaction.types import ScBatchTraining
from bpuverify.sc.transaction.types import ScBranchFeedback
from bpuverify.sc.transaction.types import ScTraining
from bpuverify.sc.coverage.catalog import sc_same_way_double_update_coverage_model
from bpuverify.sc.coverage.catalog import write_sc_same_way_double_update_coverage
from bpuverify.sc.case.definitions import NOT_TAKEN_ATTEMPTS
from bpuverify.sc.case.definitions import PC
from bpuverify.sc.case.definitions import TAGE_COUNTER
from bpuverify.common.env.paths import REPO_ROOT


POSITIONS = (1, 4)
LAYOUT = tuple(ScBaseBranch(position, TAGE_COUNTER) for position in POSITIONS)


async def beats_to_not_taken(agent, *, both_branches: bool):
    await agent.reset()
    prediction = await agent.predict_branches(PC, LAYOUT)
    assert prediction.useds[:2] == (0, 0)
    assert prediction.meta["tagePredValid"][:2] == (1, 1)
    assert prediction.meta["sumAboveThres"][:2] == (0, 0)
    assert prediction.meta["scBiasLowerBits"][0] == prediction.meta["scBiasLowerBits"][1]
    cold_signature = (
        prediction.takens[:2],
        prediction.meta["scPred"][:2],
        prediction.meta["sumAboveThres"][:2],
    )
    feedback = tuple(
        ScBranchFeedback(position, 0, prediction_slot=slot)
        for slot, position in enumerate(POSITIONS)
    )
    for beats in range(1, NOT_TAKEN_ATTEMPTS + 1):
        if both_branches:
            await agent.train_batch(ScBatchTraining(PC, prediction.meta, feedback))
        else:
            await agent.train(ScTraining(PC, POSITIONS[0], 0, prediction.meta))
        prediction = await agent.predict_branches(PC, LAYOUT)
        assert prediction.useds[0] == prediction.useds[1]
        assert prediction.takens[0] == prediction.takens[1]
        if prediction.useds[:2] == (1, 1) and prediction.takens[:2] == (0, 0):
            return beats, cold_signature, prediction
    raise AssertionError(
        f"SC did not learn not-taken with both_branches={both_branches}: "
        f"prediction={prediction!r}"
    )


@pytest.mark.feature("BPU-SC-015")
async def test_two_same_way_updates_learn_faster_than_single_feedback(sc_agent):
    coverage = sc_same_way_double_update_coverage_model()
    serial_beats, serial_cold, serial_prediction = await beats_to_not_taken(
        sc_agent, both_branches=False
    )
    assert serial_prediction.useds[:2] == (1, 1)
    coverage.sample({"phase": "single_feedback_control"})

    parallel_beats, parallel_cold, parallel_prediction = await beats_to_not_taken(
        sc_agent, both_branches=True
    )
    assert parallel_cold == serial_cold
    assert parallel_prediction.useds[:2] == (1, 1)
    assert parallel_prediction.takens[:2] == (0, 0)
    coverage.sample({"phase": "two_branch_feedback"})

    assert parallel_beats < serial_beats, (
        f"same-way feedback did not aggregate two decrements: "
        f"single={serial_beats}, both={parallel_beats}"
    )
    coverage.sample({"phase": "fewer_accepts"})

    # A third reset repeats the scalar control, proving the speedup is not
    # leftover training hidden behind an apparently cold second lookup.
    repeat_beats, repeat_cold, repeat_prediction = await beats_to_not_taken(
        sc_agent, both_branches=False
    )
    assert repeat_cold == serial_cold
    assert repeat_beats == serial_beats
    assert repeat_prediction.useds[:2] == (1, 1)
    coverage.sample({"phase": "reset_reproducible"})

    coverage.assert_coverage(100.0)
    write_sc_same_way_double_update_coverage(coverage, REPO_ROOT)
