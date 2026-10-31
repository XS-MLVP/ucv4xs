"""Same-PC TAGE feedback must respect distinct real path-history contexts."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.coverage.catalog import bpu_history_feedback_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_history_feedback_coverage
from suites.frontend.bpu.bpu.checker.assertions import mbtb_counter_for_position
from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect
from suites.frontend.bpu.bpu.checker.assertions import tage_meta_for_position
from suites.frontend.bpu.bpu.case.definitions import EARLIER_TARGET
from suites.frontend.bpu.bpu.case.definitions import PC
from suites.frontend.bpu.bpu.case.definitions import POSITION
from suites.frontend.bpu.bpu.case.scenarios import prepare_history_tage_providers
from suites.frontend.bpu.bpu.case.scenarios import revisit_via_history_path
from suites.frontend.bpu.runtime.paths import REPO_ROOT


def provider_signature(transaction):
    meta = tage_meta_for_position(transaction, POSITION)
    assert meta["hasProvider"] == 1, meta
    return (
        meta["providerTableIdx"],
        meta["providerWayIdx"],
        meta["providerTakenCtr_value"],
    )


@pytest.mark.feature("BPU-INT-028")
async def test_adjacent_feedback_keeps_two_phr_contexts_separate(bpu_agent):
    coverage = bpu_history_feedback_coverage_model()
    contexts = await prepare_history_tage_providers(bpu_agent)
    prepared = contexts.prepared
    anchor = contexts.anchor
    alternate_cold = contexts.alternate_cold
    first = contexts.first
    second = contexts.second
    anchor_provider = provider_signature(anchor)
    assert anchor_provider[2] == 2
    coverage.sample({"phase": "reference_provider"})

    assert alternate_cold.prediction.start_pc == anchor.prediction.start_pc == PC
    assert alternate_cold.meta.resolve["phr"] != anchor.meta.resolve["phr"]
    assert mbtb_counter_for_position(alternate_cold, POSITION) == 0
    assert tage_meta_for_position(alternate_cold, POSITION)["hasProvider"] == 0
    coverage.sample({"phase": "alternate_history_miss"})

    assert first.meta.resolve["phr"] == anchor.meta.resolve["phr"]
    assert second.meta.resolve["phr"] == alternate_cold.meta.resolve["phr"]
    first_provider = provider_signature(first)
    second_provider = provider_signature(second)
    assert first_provider == anchor_provider
    # RTL allocation filters candidate tables with a running LFSR. The
    # independent history cell may use a different table after a change in
    # accepted training timing; its own readback and counter are the invariant.
    assert second_provider[2] == 4
    assert first.prediction.taken == second.prediction.taken == 0
    assert mbtb_counter_for_position(first, POSITION) == (
        mbtb_counter_for_position(second, POSITION)
    ) == 1
    coverage.sample({"phase": "separate_provider_cells"})

    accepted_ticks = await bpu_agent.train_batches_with_prediction_pause((
        BpuBatchTraining(
            PC, first.meta.resolve,
            (BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),),
        ),
        BpuBatchTraining(
            PC, second.meta.resolve,
            (BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),),
        ),
    ))
    assert accepted_ticks[1] == accepted_ticks[0] + 2, accepted_ticks
    coverage.sample({"phase": "adjacent_acceptance"})

    first_after = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    second_after = await revisit_via_history_path(
        bpu_agent, PC, contexts.via_pc, anchor.meta.redirect
    )
    assert first_after.meta.resolve["phr"] == first.meta.resolve["phr"]
    assert second_after.meta.resolve["phr"] == second.meta.resolve["phr"]
    assert provider_signature(first_after) == (*first_provider[:2], 1)
    assert provider_signature(second_after) == (*second_provider[:2], 3)
    assert mbtb_counter_for_position(first_after, POSITION) == (
        mbtb_counter_for_position(second_after, POSITION)
    ) == 0
    coverage.sample({"phase": "both_contexts_updated"})

    coverage.assert_coverage(100.0)
    write_bpu_history_feedback_coverage(coverage, REPO_ROOT)
