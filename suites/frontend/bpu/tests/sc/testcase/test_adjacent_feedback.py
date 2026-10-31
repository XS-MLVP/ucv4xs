"""SC feedback bursts must eventually learn both ways of a shared row."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.sc.transaction.types import ScBaseBranch
from suites.frontend.bpu.sc.transaction.types import ScBatchTraining
from suites.frontend.bpu.sc.transaction.types import ScBranchFeedback
from suites.frontend.bpu.sc.coverage.catalog import sc_adjacent_feedback_coverage_model
from suites.frontend.bpu.sc.coverage.catalog import write_sc_adjacent_feedback_coverage
from suites.frontend.bpu.sc.case.definitions import NOT_TAKEN_ATTEMPTS
from suites.frontend.bpu.sc.case.definitions import PC
from suites.frontend.bpu.sc.case.definitions import TAGE_COUNTER
from suites.frontend.bpu.runtime.paths import REPO_ROOT


POSITIONS = (4, 5)
LAYOUT = tuple(ScBaseBranch(position, TAGE_COUNTER) for position in POSITIONS)


def feedback(meta, slot: int) -> ScBatchTraining:
    return ScBatchTraining(
        PC,
        meta,
        (ScBranchFeedback(POSITIONS[slot], 0, prediction_slot=slot),),
    )


async def learn_two_ways(agent, *, adjacent: bool, limit: int):
    await agent.reset()
    prediction = await agent.predict_branches(PC, LAYOUT)
    assert prediction.useds[:2] == (0, 0)
    assert prediction.meta["tagePredValid"][:2] == (1, 1)
    cold = prediction.takens[:2], prediction.meta["scPred"][:2]
    for rounds in range(1, limit + 1):
        first, second = feedback(prediction.meta, 0), feedback(prediction.meta, 1)
        # Eight consecutive beats keep the SRAM read port busy while earlier
        # updates are pending, so later writes exercise write-buffer merging.
        if adjacent:
            await agent.train_batches((first, second) * 4)
        else:
            for _ in range(4):
                await agent.train_batch(first)
                await agent.train_batch(second)
        prediction = await agent.predict_branches(PC, LAYOUT)
        if prediction.useds[:2] == (1, 1) and prediction.takens[:2] == (0, 0):
            return rounds, cold, prediction
    raise AssertionError(
        f"SC lost one of two {'adjacent' if adjacent else 'serial'} way updates: "
        f"{prediction!r}"
    )


@pytest.mark.feature("BPU-SC-016")
async def test_adjacent_feedback_merges_distinct_sc_ways(sc_agent):
    coverage = sc_adjacent_feedback_coverage_model()
    adjacent_rounds, adjacent_cold, adjacent_result = await learn_two_ways(
        sc_agent, adjacent=True, limit=NOT_TAKEN_ATTEMPTS
    )
    assert adjacent_cold == ((1, 1), (1, 1))
    coverage.sample({"phase": "cold"})
    assert adjacent_result.useds[:2] == (1, 1)
    assert adjacent_result.takens[:2] == (0, 0)
    coverage.sample({"phase": "both_ways_learned"})

    serial_rounds, serial_cold, serial_result = await learn_two_ways(
        sc_agent, adjacent=False, limit=adjacent_rounds
    )
    assert serial_cold == adjacent_cold
    # Consecutive train reads may see the same pre-write SRAM value. The
    # contract here is convergence of both ways, not serial-equivalent speed.
    assert serial_rounds <= adjacent_rounds
    assert serial_result.useds[:2] == adjacent_result.useds[:2]
    assert serial_result.takens[:2] == adjacent_result.takens[:2]
    coverage.sample({"phase": "serial_control"})
    coverage.assert_coverage(100.0)
    write_sc_adjacent_feedback_coverage(coverage, REPO_ROOT)
