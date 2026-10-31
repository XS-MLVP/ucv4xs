"""Integrated FTQ feedback must update two distinct TAGE provider cells."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.coverage.catalog import bpu_tage_batch_feedback_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_tage_batch_feedback_coverage
from suites.frontend.bpu.bpu.checker.assertions import mbtb_counter_for_position
from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect
from suites.frontend.bpu.bpu.checker.assertions import tage_meta_for_position
from suites.frontend.bpu.bpu.case.definitions import EARLIER_TARGET
from suites.frontend.bpu.bpu.case.definitions import LATER_POSITION
from suites.frontend.bpu.bpu.case.definitions import LATER_TARGET
from suites.frontend.bpu.bpu.case.definitions import PC
from suites.frontend.bpu.bpu.case.definitions import POSITION
from suites.frontend.bpu.bpu.case.scenarios import prepare_two_tage_providers
from suites.frontend.bpu.runtime.paths import REPO_ROOT


def provider_cell(meta):
    assert meta["hasProvider"] == 1, meta
    return meta["providerTableIdx"], meta["providerWayIdx"]


@pytest.mark.feature("BPU-INT-021")
async def test_integrated_batch_feedback_updates_both_tage_providers(bpu_agent):
    coverage = bpu_tage_batch_feedback_coverage_model()
    prepared = await prepare_two_tage_providers(bpu_agent)
    # The scenario helper asserts each public intermediate readback before
    # the next feedback is sent; these bins describe its verified milestones.
    assert mbtb_counter_for_position(prepared.first_resident, POSITION) == 2
    coverage.sample({"phase": "two_mbtb_residents"})
    assert tage_meta_for_position(prepared.single_provider, POSITION)["providerTakenCtr_value"] == 4
    coverage.sample({"phase": "single_provider_control"})
    both = prepared.both_providers
    earlier = tage_meta_for_position(both, POSITION)
    later = tage_meta_for_position(both, LATER_POSITION)
    earlier_cell = provider_cell(earlier)
    later_cell = provider_cell(later)
    assert earlier_cell != later_cell
    assert (earlier["providerTakenCtr_value"], later["providerTakenCtr_value"]) == (2, 3)
    coverage.sample({"phase": "two_distinct_providers"})

    # One FTQ feedback beat updates both already-resident TAGE cells. Pair
    # each public TAGE metadata entry to its MainBTB raw-hit position.
    await bpu_agent.train_batch_with_prediction_pause(
        BpuBatchTraining(
            PC, both.meta.resolve,
            (
                BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),
                None,
                BpuBranchFeedback(LATER_POSITION, LATER_TARGET, 1, taken=0),
            ),
        )
    )
    updated = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    assert (
        mbtb_counter_for_position(updated, POSITION),
        mbtb_counter_for_position(updated, LATER_POSITION),
    ) == (0, 0)
    earlier = tage_meta_for_position(updated, POSITION)
    later = tage_meta_for_position(updated, LATER_POSITION)
    assert (*provider_cell(earlier), earlier["providerTakenCtr_value"]) == (
        *earlier_cell, 1,
    )
    assert (*provider_cell(later), later["providerTakenCtr_value"]) == (
        *later_cell, 2,
    )
    coverage.sample({"phase": "both_provider_counters_updated"})

    coverage.assert_coverage(100.0)
    write_bpu_tage_batch_feedback_coverage(coverage, REPO_ROOT)
