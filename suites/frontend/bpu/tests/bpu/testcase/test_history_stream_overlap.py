"""Two TAGE history-feedback beats overlap a prediction stream on another bank."""

from __future__ import annotations

import pytest

from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.coverage.catalog import bpu_history_stream_overlap_coverage_model
from bpuverify.bpu.coverage.catalog import write_bpu_history_stream_overlap_coverage
from bpuverify.bpu.checker.assertions import revisit_from_redirect
from bpuverify.bpu.checker.assertions import tage_meta_for_position
from bpuverify.bpu.case.definitions import EARLIER_TARGET
from bpuverify.bpu.case.definitions import PC
from bpuverify.bpu.case.definitions import POSITION
from bpuverify.bpu.case.definitions import REDIRECT_PC
from bpuverify.bpu.case.scenarios import prepare_history_tage_providers
from bpuverify.bpu.case.scenarios import revisit_via_history_path
from bpuverify.common.env.paths import REPO_ROOT


QUIET_PC = REDIRECT_PC + 2


def provider_signature(transaction):
    meta = tage_meta_for_position(transaction, POSITION)
    assert meta["hasProvider"] == 1, meta
    return (
        meta["providerTableIdx"],
        meta["providerWayIdx"],
        meta["providerTakenCtr_value"],
    )


@pytest.mark.feature("BPU-INT-029")
async def test_distinct_history_feedback_overlaps_other_bank_predictions(bpu_agent):
    coverage = bpu_history_stream_overlap_coverage_model()
    contexts = await prepare_history_tage_providers(bpu_agent)
    assert contexts.first.meta.resolve["phr"] != contexts.second.meta.resolve["phr"]
    first_provider = provider_signature(contexts.first)
    second_provider = provider_signature(contexts.second)
    # Allocation uses a free-running LFSR; table/way are a captured identity,
    # not a timing-dependent constant. Preserve that identity across updates.
    assert first_provider[2] == 2
    assert second_provider[2] == 4
    coverage.sample({"phase": "two_history_cells_prepared"})

    # TAGE has four banks indexed by PC bits [2:1] in this configuration.
    # The nonconditional self-loop stays on bank 1 while both feedback beats
    # update provider cells for PC on bank 0.
    assert (PC >> 1) & 3 == 0
    assert (QUIET_PC >> 1) & 3 == 1
    quiet_cold = await revisit_from_redirect(
        bpu_agent, QUIET_PC, contexts.anchor.meta.redirect
    )
    assert quiet_cold.prediction.taken == 0
    await bpu_agent.train(BpuTraining(
        QUIET_PC, POSITION, QUIET_PC, quiet_cold.meta.resolve,
    ))
    await bpu_agent.redirect_and_settle(BpuRedirect(
        QUIET_PC, quiet_cold.meta.redirect
    ))

    activity = await bpu_agent.train_batches_during_stream((
        BpuBatchTraining(
            PC, contexts.first.meta.resolve,
            (BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),),
        ),
        BpuBatchTraining(
            PC, contexts.second.meta.resolve,
            (BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),),
        ),
    ))
    ticks = activity.training_ticks
    assert ticks[1] == ticks[0] + 2, ticks
    coverage.sample({"phase": "adjacent_feedback"})
    assert activity.prediction_ticks == ticks, activity
    assert all(pred.start_pc == QUIET_PC for pred in activity.predictions), activity
    coverage.sample({"phase": "bank_disjoint_stream"})
    coverage.sample({"phase": "prediction_overlap"})

    first_after = await revisit_from_redirect(
        bpu_agent, PC, contexts.prepared.cold.meta.redirect
    )
    second_after = await revisit_via_history_path(
        bpu_agent, PC, contexts.via_pc, contexts.anchor.meta.redirect
    )
    assert first_after.meta.resolve["phr"] == contexts.first.meta.resolve["phr"]
    assert second_after.meta.resolve["phr"] == contexts.second.meta.resolve["phr"]
    assert provider_signature(first_after) == (*first_provider[:2], 1)
    assert provider_signature(second_after) == (*second_provider[:2], 3)
    coverage.sample({"phase": "both_cells_updated"})

    coverage.assert_coverage(100.0)
    write_bpu_history_stream_overlap_coverage(coverage, REPO_ROOT)
