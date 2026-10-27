"""Two separately resolved FTQ beats enter the integrated training pipeline."""

from __future__ import annotations

import pytest

from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.coverage.catalog import bpu_adjacent_feedback_coverage_model
from bpuverify.bpu.coverage.catalog import write_bpu_adjacent_feedback_coverage
from bpuverify.bpu.checker.assertions import mbtb_counter_for_position
from bpuverify.bpu.checker.assertions import revisit_from_redirect
from bpuverify.bpu.checker.assertions import tage_provider_signatures
from bpuverify.bpu.case.definitions import EARLIER_TARGET
from bpuverify.bpu.case.definitions import LATER_POSITION
from bpuverify.bpu.case.definitions import LATER_TARGET
from bpuverify.bpu.case.definitions import PC
from bpuverify.bpu.case.definitions import POSITION
from bpuverify.bpu.case.scenarios import prepare_two_tage_providers
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-INT-026")
async def test_adjacent_feedback_beats_update_distinct_tage_cells(bpu_agent):
    coverage = bpu_adjacent_feedback_coverage_model()
    prepared = await prepare_two_tage_providers(bpu_agent)
    first = prepared.both_providers
    second = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    positions = (POSITION, LATER_POSITION)
    before = tage_provider_signatures(first, positions)
    assert before == tage_provider_signatures(second, positions)
    assert first.meta_tick == first.prediction_tick + 4
    assert second.meta_tick == second.prediction_tick + 4
    assert second.prediction_tick > first.prediction_tick
    assert before[0][:2] != before[1][:2]
    assert (before[0][2], before[1][2]) == (2, 3)
    coverage.sample({"phase": "distinct_paired_metadata"})

    # Each beat carries its own accepted S3 resolve snapshot. The agent queues
    # both before awaiting acceptance; driver ownership keeps pin timing out
    # of the test and preserves ready/valid backpressure semantics.
    accepted_ticks = await bpu_agent.train_batches_with_prediction_pause((
        BpuBatchTraining(
            PC, first.meta.resolve,
            (BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),),
        ),
        BpuBatchTraining(
            PC, second.meta.resolve,
            (None, None, BpuBranchFeedback(
                LATER_POSITION, LATER_TARGET, 1, taken=0,
            )),
        ),
    ))
    # Reactor ticks count clock edges, so adjacent rising edges differ by 2.
    assert accepted_ticks[1] == accepted_ticks[0] + 2, accepted_ticks
    coverage.sample({"phase": "adjacent_acceptance"})

    updated = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    after = tage_provider_signatures(updated, positions)
    assert tuple(signature[:2] for signature in after) == tuple(
        signature[:2] for signature in before
    )
    assert tuple(signature[2] for signature in after) == (1, 2), after
    coverage.sample({"phase": "both_provider_cells_updated"})
    assert tuple(
        mbtb_counter_for_position(updated, position) for position in positions
    ) == (0, 0)
    coverage.sample({"phase": "both_mbtb_slots_updated"})

    coverage.assert_coverage(100.0)
    write_bpu_adjacent_feedback_coverage(coverage, REPO_ROOT)
