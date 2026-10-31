"""Integrated FTQ feedback must reach both SC prediction positions."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.coverage.catalog import bpu_sc_batch_feedback_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_sc_batch_feedback_coverage
from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect
from suites.frontend.bpu.bpu.checker.assertions import sc_meta_for_position
from suites.frontend.bpu.bpu.checker.assertions import tage_provider_signatures
from suites.frontend.bpu.bpu.case.definitions import EARLIER_TARGET
from suites.frontend.bpu.bpu.case.definitions import LATER_POSITION
from suites.frontend.bpu.bpu.case.definitions import LATER_TARGET
from suites.frontend.bpu.bpu.case.definitions import PC
from suites.frontend.bpu.bpu.case.definitions import POSITION
from suites.frontend.bpu.bpu.case.scenarios import prepare_two_tage_providers
from suites.frontend.bpu.bpu.case.scenarios import train_sc_feedback_with_tage_held
from suites.frontend.bpu.runtime.paths import REPO_ROOT


SC_TRAINING_BEATS = 32


def sc_pair(transaction):
    return tuple(
        sc_meta_for_position(transaction, position)
        for position in (POSITION, LATER_POSITION)
    )


async def sc_ready_transaction(agent, prepared):
    await agent.configure_predictors(sc=True, settle=True)
    current = await revisit_from_redirect(
        agent, PC, prepared.cold.meta.redirect
    )
    assert sc_pair(current) == (
        {
            "tagePredValid": 1, "tageCtr": 2, "scPred": 1,
            "useScPred": 0, "sumAboveThres": 0,
        },
        {
            "tagePredValid": 1, "tageCtr": 3, "scPred": 1,
            "useScPred": 0, "sumAboveThres": 0,
        },
    )
    assert tuple(signature[2] for signature in tage_provider_signatures(
        current, (POSITION, LATER_POSITION)
    )) == (2, 3)
    return current


@pytest.mark.feature("BPU-INT-022")
async def test_integrated_dual_branch_feedback_trains_both_sc_slots(bpu_agent):
    coverage = bpu_sc_batch_feedback_coverage_model()

    # Control: a single resolved branch may train its own SC way, but must
    # leave the later, differently mapped provider/SC way unchanged.
    prepared = await prepare_two_tage_providers(bpu_agent)
    before = await sc_ready_transaction(bpu_agent, prepared)
    baseline_providers = tage_provider_signatures(before, (POSITION, LATER_POSITION))
    coverage.sample({"phase": "two_providers_qualified"})
    await train_sc_feedback_with_tage_held(
        bpu_agent, before,
        (BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),),
        repetitions=SC_TRAINING_BEATS,
    )
    single = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    assert sc_pair(single) == (
        {
            "tagePredValid": 1, "tageCtr": 2, "scPred": 0,
            "useScPred": 1, "sumAboveThres": 1,
        },
        {
            "tagePredValid": 1, "tageCtr": 3, "scPred": 1,
            "useScPred": 0, "sumAboveThres": 0,
        },
    )
    assert tage_provider_signatures(single, (POSITION, LATER_POSITION)) == baseline_providers
    coverage.sample({"phase": "single_branch_control"})

    # Reset and reproduce the same cold two-provider state, then train both
    # positions in each FTQ beat with a vacant resolved slot between them.
    prepared = await prepare_two_tage_providers(bpu_agent)
    before_dual = await sc_ready_transaction(bpu_agent, prepared)
    assert tage_provider_signatures(before_dual, (POSITION, LATER_POSITION)) == baseline_providers
    await train_sc_feedback_with_tage_held(
        bpu_agent, before_dual,
        (
            BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),
            None,
            BpuBranchFeedback(LATER_POSITION, LATER_TARGET, 1, taken=0),
        ),
        repetitions=SC_TRAINING_BEATS,
    )
    dual = await revisit_from_redirect(
        bpu_agent, PC, prepared.cold.meta.redirect
    )
    assert sc_pair(dual) == (
        {
            "tagePredValid": 1, "tageCtr": 2, "scPred": 0,
            "useScPred": 1, "sumAboveThres": 1,
        },
        {
            "tagePredValid": 1, "tageCtr": 3, "scPred": 0,
            "useScPred": 1, "sumAboveThres": 1,
        },
    )
    coverage.sample({"phase": "same_beat_dual_feedback"})
    assert tage_provider_signatures(dual, (POSITION, LATER_POSITION)) == baseline_providers
    coverage.sample({"phase": "provider_state_held"})

    coverage.assert_coverage(100.0)
    write_bpu_sc_batch_feedback_coverage(coverage, REPO_ROOT)
