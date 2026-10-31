"""A single FTQ feedback beat updates two different TAGE providers."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.tage.transaction.types import TageBatchTraining
from suites.frontend.bpu.tage.transaction.types import TageBranchFeedback
from suites.frontend.bpu.tage.transaction.types import TageTraining
from suites.frontend.bpu.tage.coverage.catalog import tage_batch_feedback_coverage_model
from suites.frontend.bpu.tage.coverage.catalog import write_tage_batch_feedback_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.case.definitions import PC
from suites.frontend.bpu.tage.case.definitions import POSITION


@pytest.mark.feature("BPU-TAGE-017")
async def test_two_conditional_providers_update_in_one_feedback_beat(tage_agent):
    coverage = tage_batch_feedback_coverage_model()
    await tage_agent.reset()
    earlier_position, later_position = POSITION, POSITION + 1

    # The earlier branch falls through; the later branch is taken. Each gets
    # its own provider through ordinary single-branch training first.
    cold_earlier = await tage_agent.predict(PC, earlier_position, 1)
    assert cold_earlier.meta["hasProvider"] == 0
    await tage_agent.train(
        TageTraining(PC, earlier_position, 0, 1, cold_earlier.meta)
    )
    cold_later = await tage_agent.predict(PC, later_position, 0)
    assert cold_later.meta["hasProvider"] == 0
    await tage_agent.train(
        TageTraining(PC, later_position, 1, 0, cold_later.meta)
    )

    # Once each base counter has followed its outcome, a correct individual
    # feedback strengthens the weak provider before the vector experiment.
    weak_earlier = await tage_agent.predict(PC, earlier_position, 0)
    weak_later = await tage_agent.predict(PC, later_position, 1)
    assert weak_earlier.meta["providerTakenCtr_value"] == 3
    assert weak_later.meta["providerTakenCtr_value"] == 4
    await tage_agent.train(
        TageTraining(PC, earlier_position, 0, 0, weak_earlier.meta, mispredict=0)
    )
    await tage_agent.train(
        TageTraining(PC, later_position, 1, 1, weak_later.meta, mispredict=0)
    )

    earlier = await tage_agent.predict(PC, earlier_position, 0)
    later = await tage_agent.predict(PC, later_position, 1)
    assert earlier.meta["hasProvider"] == later.meta["hasProvider"] == 1
    assert (earlier.valid, earlier.taken) == (1, 0)
    assert (later.valid, later.taken) == (1, 1)
    earlier_cell = (earlier.meta["providerTableIdx"], earlier.meta["providerWayIdx"])
    later_cell = (later.meta["providerTableIdx"], later.meta["providerWayIdx"])
    assert earlier_cell != later_cell
    assert earlier.meta["providerTakenCtr_value"] == 2
    assert later.meta["providerTakenCtr_value"] == 5
    coverage.sample({"phase": "two_residents"})

    # Both branches are correctly predicted, so neither asks for allocation.
    # Their distinct metadata must be selected by the two MainBTB hit slots,
    # even though the resolve vector has a vacant slot between the branches.
    await tage_agent.train_batch(
        TageBatchTraining(
            PC,
            (
                TageBranchFeedback(earlier_position, 0, 0, earlier.meta),
                None,
                TageBranchFeedback(later_position, 1, 1, later.meta),
            ),
        )
    )
    updated_earlier = await tage_agent.predict(PC, earlier_position, 0)
    updated_later = await tage_agent.predict(PC, later_position, 1)
    assert (
        updated_earlier.meta["providerTableIdx"],
        updated_earlier.meta["providerWayIdx"],
        updated_earlier.meta["providerTakenCtr_value"],
    ) == (*earlier_cell, 1)
    assert (
        updated_later.meta["providerTableIdx"],
        updated_later.meta["providerWayIdx"],
        updated_later.meta["providerTakenCtr_value"],
    ) == (*later_cell, 6)
    coverage.sample({"phase": "both_correct"})

    # A second beat proves the first was not a coincidental single-branch
    # write: both cells must independently continue toward saturation.
    await tage_agent.train_batch(
        TageBatchTraining(
            PC,
            (
                TageBranchFeedback(earlier_position, 0, 0, updated_earlier.meta),
                TageBranchFeedback(later_position, 1, 1, updated_later.meta),
            ),
        )
    )
    final_earlier = await tage_agent.predict(PC, earlier_position, 0)
    final_later = await tage_agent.predict(PC, later_position, 1)
    assert final_earlier.meta["providerTakenCtr_value"] == 0
    assert final_later.meta["providerTakenCtr_value"] == 7
    assert (
        final_earlier.meta["providerTableIdx"], final_earlier.meta["providerWayIdx"]
    ) == earlier_cell
    assert (
        final_later.meta["providerTableIdx"], final_later.meta["providerWayIdx"]
    ) == later_cell
    coverage.sample({"phase": "independent_counters"})

    coverage.assert_coverage(100.0)
    write_tage_batch_feedback_coverage(coverage, REPO_ROOT)
