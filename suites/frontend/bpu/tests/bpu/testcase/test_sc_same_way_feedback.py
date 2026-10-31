"""Integrated FTQ feedback aggregates two conditions mapped to one SC way."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.coverage.catalog import bpu_sc_same_way_feedback_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_sc_same_way_feedback_coverage
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


@pytest.mark.feature("BPU-INT-023")
async def test_integrated_same_way_sc_aggregates_two_branch_updates(bpu_agent):
    coverage = bpu_sc_same_way_feedback_coverage_model()
    earlier_position, later_position = SC_SAME_WAY_POSITIONS

    prepared = await prepare_same_way_sc_providers(bpu_agent)
    baseline_providers = tage_provider_signatures(
        prepared.qualified, SC_SAME_WAY_POSITIONS
    )
    assert baseline_providers[0][:2] != baseline_providers[1][:2]
    assert (baseline_providers[0][2], baseline_providers[1][2]) == (2, 2)
    assert sc_decisions_for_positions(
        prepared.qualified, SC_SAME_WAY_POSITIONS
    ) == ((1, 0, 0), (1, 0, 0))
    coverage.sample({"phase": "qualified_pair"})

    single_feedback = (
        BpuBranchFeedback(earlier_position, EARLIER_TARGET, 1, taken=0),
    )
    await train_sc_feedback_with_tage_held(
        bpu_agent, prepared.qualified, single_feedback, repetitions=4
    )
    single_four = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    assert sc_decisions_for_positions(
        single_four, SC_SAME_WAY_POSITIONS
    ) == ((0, 0, 0), (0, 0, 0))
    assert tage_provider_signatures(single_four, SC_SAME_WAY_POSITIONS) == (
        baseline_providers
    )
    coverage.sample({"phase": "single_four_pending"})

    # A second four-beat scalar replay proves the SC way is trainable; the
    # first four beats simply did not cross its use threshold.
    await train_sc_feedback_with_tage_held(
        bpu_agent, prepared.qualified, single_feedback, repetitions=4
    )
    single_eight = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    assert sc_decisions_for_positions(
        single_eight, SC_SAME_WAY_POSITIONS
    ) == ((0, 1, 1), (0, 1, 1))
    assert tage_provider_signatures(single_eight, SC_SAME_WAY_POSITIONS) == (
        baseline_providers
    )
    coverage.sample({"phase": "single_eight_learned"})

    # Recreate exactly the same qualified metadata. Four feedback beats now
    # contain both not-taken branches in resolved slots 0 and 2; slot 1 is
    # invalid. The shared SC way must cross its threshold twice as fast.
    prepared = await prepare_same_way_sc_providers(bpu_agent)
    assert tage_provider_signatures(
        prepared.qualified, SC_SAME_WAY_POSITIONS
    ) == baseline_providers
    assert sc_decisions_for_positions(
        prepared.qualified, SC_SAME_WAY_POSITIONS
    ) == ((1, 0, 0), (1, 0, 0))
    await train_sc_feedback_with_tage_held(
        bpu_agent,
        prepared.qualified,
        (
            BpuBranchFeedback(earlier_position, EARLIER_TARGET, 1, taken=0),
            None,
            BpuBranchFeedback(later_position, LATER_TARGET, 1, taken=0),
        ),
        repetitions=4,
    )
    dual_four = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    assert sc_decisions_for_positions(
        dual_four, SC_SAME_WAY_POSITIONS
    ) == ((0, 1, 1), (0, 1, 1))
    coverage.sample({"phase": "dual_four_learned"})
    assert tage_provider_signatures(dual_four, SC_SAME_WAY_POSITIONS) == (
        baseline_providers
    )
    coverage.sample({"phase": "provider_state_held"})

    coverage.assert_coverage(100.0)
    write_bpu_sc_same_way_feedback_coverage(coverage, REPO_ROOT)
