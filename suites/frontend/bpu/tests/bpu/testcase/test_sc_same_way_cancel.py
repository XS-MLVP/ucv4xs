"""Opposite FTQ outcomes cancel when two branches share one SC way."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.coverage.catalog import bpu_sc_same_way_cancel_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_sc_same_way_cancel_coverage
from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect
from suites.frontend.bpu.bpu.checker.assertions import sc_decisions_for_positions
from suites.frontend.bpu.bpu.checker.assertions import tage_provider_signatures
from suites.frontend.bpu.bpu.case.definitions import EARLIER_TARGET
from suites.frontend.bpu.bpu.case.definitions import LATER_TARGET
from suites.frontend.bpu.bpu.case.definitions import PC
from suites.frontend.bpu.bpu.case.definitions import SC_SAME_WAY_POSITIONS
from suites.frontend.bpu.bpu.case.scenarios import prepare_same_way_sc_providers
from suites.frontend.bpu.bpu.case.scenarios import train_sc_feedback_with_tage_held
from suites.frontend.bpu.runtime.paths import REPO_ROOT


SC_COLD = ((1, 0, 0), (1, 0, 0))
SC_NOT_TAKEN = ((0, 1, 1), (0, 1, 1))


@pytest.mark.feature("BPU-INT-024")
async def test_integrated_opposite_same_way_sc_feedback_cancels(bpu_agent):
    coverage = bpu_sc_same_way_cancel_coverage_model()
    earlier_position, later_position = SC_SAME_WAY_POSITIONS
    opposite = (
        BpuBranchFeedback(earlier_position, EARLIER_TARGET, 1, taken=0),
        None,
        BpuBranchFeedback(later_position, LATER_TARGET, 1, taken=1),
    )
    single_not_taken = (
        BpuBranchFeedback(earlier_position, EARLIER_TARGET, 1, taken=0),
    )
    dual_not_taken = (
        single_not_taken[0],
        None,
        BpuBranchFeedback(later_position, LATER_TARGET, 1, taken=0),
    )

    prepared = await prepare_same_way_sc_providers(bpu_agent)
    baseline_providers = tage_provider_signatures(
        prepared.qualified, SC_SAME_WAY_POSITIONS
    )
    assert baseline_providers[0][:2] != baseline_providers[1][:2]
    assert sc_decisions_for_positions(
        prepared.qualified, SC_SAME_WAY_POSITIONS
    ) == SC_COLD
    coverage.sample({"phase": "qualified_pair"})

    # Earlier not-taken permits execution of the later taken branch. Each
    # beat supplies one negative and one positive vote to the shared SC way.
    for repetitions in (4, 4, 8, 16, 32):
        await train_sc_feedback_with_tage_held(
            bpu_agent, prepared.qualified, opposite,
            repetitions=repetitions,
        )
        observed = await revisit_from_redirect(
            bpu_agent, PC, prepared.cold.meta.redirect
        )
        assert sc_decisions_for_positions(
            observed, SC_SAME_WAY_POSITIONS
        ) == SC_COLD
        assert tage_provider_signatures(
            observed, SC_SAME_WAY_POSITIONS
        ) == baseline_providers
    coverage.sample({"phase": "opposite_feedback_cancelled"})

    # The same SC way is still trainable after 64 cancelling beats.
    await train_sc_feedback_with_tage_held(
        bpu_agent, prepared.qualified, single_not_taken, repetitions=8
    )
    scalar = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    assert sc_decisions_for_positions(
        scalar, SC_SAME_WAY_POSITIONS
    ) == SC_NOT_TAKEN
    assert tage_provider_signatures(
        scalar, SC_SAME_WAY_POSITIONS
    ) == baseline_providers
    coverage.sample({"phase": "single_branch_control"})

    # A fresh qualified state reproduces cancellation. Changing only the
    # later outcome to not-taken then makes the same two-slot vector train
    # the shared way in four beats, excluding an ignored-vector false pass.
    prepared = await prepare_same_way_sc_providers(bpu_agent)
    assert tage_provider_signatures(
        prepared.qualified, SC_SAME_WAY_POSITIONS
    ) == baseline_providers
    assert sc_decisions_for_positions(
        prepared.qualified, SC_SAME_WAY_POSITIONS
    ) == SC_COLD
    coverage.sample({"phase": "reset_reproducible"})
    await train_sc_feedback_with_tage_held(
        bpu_agent, prepared.qualified, opposite, repetitions=64
    )
    cancelled = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    assert sc_decisions_for_positions(
        cancelled, SC_SAME_WAY_POSITIONS
    ) == SC_COLD
    await train_sc_feedback_with_tage_held(
        bpu_agent, prepared.qualified, dual_not_taken, repetitions=4
    )
    learned = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    assert sc_decisions_for_positions(
        learned, SC_SAME_WAY_POSITIONS
    ) == SC_NOT_TAKEN
    coverage.sample({"phase": "dual_vector_after_cancel"})
    assert tage_provider_signatures(
        learned, SC_SAME_WAY_POSITIONS
    ) == baseline_providers
    coverage.sample({"phase": "provider_state_held"})

    coverage.assert_coverage(100.0)
    write_bpu_sc_same_way_cancel_coverage(coverage, REPO_ROOT)
