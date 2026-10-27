"""S3 repairs an AheadBTB-sourced indirect target after MainBTB retraining."""

from __future__ import annotations

import pytest

from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.transaction.types import BpuStage1Source
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.coverage.catalog import bpu_abtb_s3_correction_coverage_model
from bpuverify.bpu.coverage.catalog import write_bpu_abtb_s3_correction_coverage
from bpuverify.common.env.paths import REPO_ROOT


PC = 0x407F_FFE0
NEW_TARGET = 0x4080_0100
POSITION = 4
LIMIT = 128


@pytest.mark.feature("BPU-INT-019")
async def test_s3_corrects_abtb_old_target_to_cross_region_main_btb_target(bpu_agent):
    coverage = bpu_abtb_s3_correction_coverage_model()
    await bpu_agent.reset(PC)
    initial = await bpu_agent.next_transaction(start_pc=PC)
    await bpu_agent.configure_predictors(ubtb=False, abtb=False, ittage=False)
    boundary = await bpu_agent.redirect(BpuRedirect(PC, initial.meta.redirect))
    cold = await bpu_agent.next_transaction(start_pc=PC, after_tick=boundary)
    assert cold.prediction.taken == 0
    await bpu_agent.train(
        BpuTraining(PC, POSITION, PC, cold.meta.resolve, branch_type=3)
    )
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    _, repair = await bpu_agent.next_prediction(
        start_pc=PC, target=PC, stage="s2", after_tick=boundary, limit=LIMIT
    )
    assert (repair.taken, repair.position) == (1, POSITION)

    await bpu_agent.configure_predictors(abtb=True)
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    _, repair = await bpu_agent.next_prediction(
        start_pc=PC, target=PC, stage="s2", after_tick=boundary, limit=LIMIT
    )
    assert repair.taken == 1
    await bpu_agent.pause_prediction_reads()
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    ahead = await bpu_agent.next_transaction(
        start_pc=PC, require_taken=True, after_tick=boundary, limit=LIMIT
    )
    assert (ahead.prediction.target, ahead.prediction.position) == (PC, POSITION)
    assert ahead.meta.perf.s1_source is BpuStage1Source.ABTB
    coverage.sample({"phase": "ahead_s1_old"})

    # Stop S0 reads while the indirect MainBTB target is updated, then let
    # the held AheadBTB prediction proceed. This avoids read-priority SRAM
    # traffic starving the MainBTB write without changing path history.
    await bpu_agent.set_ready(prediction=False, meta=True)
    await bpu_agent.train(
        BpuTraining(PC, POSITION, NEW_TARGET, ahead.meta.resolve, branch_type=3)
    )
    await bpu_agent.set_ready(prediction=True, meta=True)
    corrected = await bpu_agent.next_s3_correction(
        start_pc=PC, target=NEW_TARGET,
        after_tick=ahead.prediction_tick, limit=LIMIT,
    )
    assert (
        corrected.prediction.taken,
        corrected.prediction.position,
        corrected.prediction.s2_override,
        corrected.prediction.s3_override,
    ) == (1, POSITION, 0, 1)
    coverage.sample({"phase": "main_s3_cross_region"})
    assert (
        corrected.meta.perf.start_pc,
        corrected.meta.perf.s1_target,
        corrected.meta.perf.s1_taken,
        corrected.meta.perf.s1_position,
        corrected.meta.perf.s1_source,
    ) == (PC, PC, 1, POSITION, BpuStage1Source.ABTB)
    coverage.sample({"phase": "same_cycle_source_echo"})
    coverage.assert_coverage(100.0)
    write_bpu_abtb_s3_correction_coverage(coverage, REPO_ROOT)
