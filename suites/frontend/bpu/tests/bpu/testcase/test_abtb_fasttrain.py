"""Integrated S3 fastTrain promotes a MainBTB repair into an AheadBTB S1 hit."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.transaction.types import BpuTraining
from suites.frontend.bpu.bpu.coverage.catalog import bpu_abtb_fasttrain_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_abtb_fasttrain_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT


PC = 0x4000_0800
POSITION = 4
TARGET = PC  # A self-loop revisits the fetch block for repeated S3 fastTrain.
LIMIT = 128


@pytest.mark.feature("BPU-INT-015")
async def test_ahead_btb_learns_main_btb_repair_via_fasttrain(bpu_agent):
    coverage = bpu_abtb_fasttrain_coverage_model()
    await bpu_agent.reset(PC)
    initial = await bpu_agent.next_transaction(start_pc=PC)
    await bpu_agent.configure_predictors(ubtb=False, abtb=False, ittage=False)

    boundary = await bpu_agent.redirect(BpuRedirect(PC, initial.meta.redirect))
    cold = await bpu_agent.next_transaction(start_pc=PC, after_tick=boundary)
    assert cold.prediction.taken == 0
    await bpu_agent.train(
        BpuTraining(PC, POSITION, TARGET, cold.meta.resolve, branch_type=3)
    )

    # Neither S1 predictor can hit yet; MainBTB supplies the first repair.
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    _, initial_repair = await bpu_agent.next_prediction(
        start_pc=PC, target=TARGET, stage="s2", after_tick=boundary, limit=LIMIT
    )
    assert (initial_repair.taken, initial_repair.position) == (1, POSITION)
    coverage.sample({"source_phase": "main_btb_s2"})

    # Repeated self-loop predictions feed S3 fastTrain into the enabled ABTB.
    await bpu_agent.configure_predictors(abtb=True)
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    _, main_repair = await bpu_agent.next_prediction(
        start_pc=PC, target=TARGET, stage="s2", after_tick=boundary,
        limit=LIMIT,
    )
    assert main_repair.taken == 1
    await bpu_agent.pause_prediction_reads()

    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    _, ahead_hit = await bpu_agent.next_prediction(
        start_pc=PC, require_taken=True, stage="s1", after_tick=boundary, limit=LIMIT
    )
    assert (ahead_hit.target, ahead_hit.position) == (TARGET, POSITION)
    assert (ahead_hit.s2_override, ahead_hit.s3_override) == (0, 0)
    coverage.sample({"source_phase": "ahead_btb_s1"})

    await bpu_agent.configure_predictors(abtb=False)
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    _, fallback = await bpu_agent.next_prediction(
        start_pc=PC, target=TARGET, stage="s2", after_tick=boundary, limit=LIMIT
    )
    assert (fallback.taken, fallback.position) == (1, POSITION)
    coverage.sample({"source_phase": "main_btb_fallback"})

    coverage.assert_coverage(100.0)
    write_bpu_abtb_fasttrain_coverage(coverage, REPO_ROOT)
