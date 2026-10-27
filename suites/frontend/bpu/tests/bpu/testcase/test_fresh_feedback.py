"""Fresh paired metadata drives successive integrated TAGE and SC feedback."""

from __future__ import annotations

import pytest

from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.coverage.catalog import bpu_fresh_feedback_coverage_model
from bpuverify.bpu.coverage.catalog import write_bpu_fresh_feedback_coverage
from bpuverify.bpu.checker.assertions import mbtb_counter_for_position
from bpuverify.bpu.checker.assertions import revisit_from_redirect
from bpuverify.bpu.checker.assertions import sc_decisions_for_positions
from bpuverify.bpu.checker.assertions import sc_meta_for_position
from bpuverify.bpu.checker.assertions import tage_provider_signatures
from bpuverify.bpu.case.definitions import EARLIER_TARGET
from bpuverify.bpu.case.definitions import LATER_TARGET
from bpuverify.bpu.case.definitions import PC
from bpuverify.bpu.case.definitions import SC_SAME_WAY_POSITIONS
from bpuverify.bpu.case.scenarios import prepare_same_way_sc_providers
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-INT-025")
async def test_each_fresh_resolve_meta_updates_tage_then_sc(bpu_agent):
    coverage = bpu_fresh_feedback_coverage_model()
    earlier_position, later_position = SC_SAME_WAY_POSITIONS
    prepared = await prepare_same_way_sc_providers(bpu_agent)
    current = prepared.qualified
    cells = tuple(signature[:2] for signature in tage_provider_signatures(
        current, SC_SAME_WAY_POSITIONS
    ))
    assert cells[0] != cells[1]
    assert sc_decisions_for_positions(
        current, SC_SAME_WAY_POSITIONS
    ) == ((1, 0, 0), (1, 0, 0))
    coverage.sample({"phase": "qualified_pair"})

    feedback = (
        BpuBranchFeedback(earlier_position, EARLIER_TARGET, 1, taken=0),
        None,
        BpuBranchFeedback(later_position, LATER_TARGET, 1, taken=0),
    )
    for beat in range(1, 9):
        previous = current
        # Unlike the isolated SC tests, TAGE stays enabled and each FTQ beat
        # carries the newly accepted S3 resolve snapshot, not a replay of the
        # initial metadata. The agent pairs S1 and S3 before returning it.
        await bpu_agent.train_batch_with_prediction_pause(
            BpuBatchTraining(PC, previous.meta.resolve, feedback)
        )
        current = await revisit_from_redirect(
            bpu_agent, PC, prepared.cold.meta.redirect
        )
        assert current.prediction_tick > previous.prediction_tick
        assert current.meta_tick > previous.meta_tick
        assert current.meta_tick == current.prediction_tick + 4
        assert tuple(
            mbtb_counter_for_position(current, position)
            for position in SC_SAME_WAY_POSITIONS
        ) == (0, 0)

        signatures = tage_provider_signatures(current, SC_SAME_WAY_POSITIONS)
        assert tuple(signature[:2] for signature in signatures) == cells
        expected_counter = max(0, 2 - beat)
        assert tuple(signature[2] for signature in signatures) == (
            expected_counter, expected_counter
        )
        for position in SC_SAME_WAY_POSITIONS:
            sc_meta = sc_meta_for_position(current, position)
            assert sc_meta["tagePredValid"] == 1
            assert sc_meta["tageCtr"] == expected_counter

        expected_sc = (
            ((0, 0, 0), (0, 0, 0))
            if beat < 7 else ((0, 1, 1), (0, 1, 1))
        )
        assert sc_decisions_for_positions(
            current, SC_SAME_WAY_POSITIONS
        ) == expected_sc
        coverage.sample({"phase": "paired_metadata_advanced"})
        if beat == 2:
            coverage.sample({"phase": "both_tage_counters_saturated"})
        if beat == 7:
            coverage.sample({"phase": "sc_threshold_crossed"})
        if beat == 8:
            coverage.sample({"phase": "learned_state_persists"})

    coverage.assert_coverage(100.0)
    write_bpu_fresh_feedback_coverage(coverage, REPO_ROOT)
