"""Prove early-predictor training isolation with distinct target values."""

from __future__ import annotations

import pytest

from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.transaction.types import BpuStage1Source
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.coverage.catalog import bpu_early_source_isolation_coverage_model
from bpuverify.bpu.coverage.catalog import write_bpu_early_source_isolation_coverage
from bpuverify.common.env.paths import REPO_ROOT


PC = 0x4000_0800
QUIET_PC = 0x4001_8000
POSITION = 4
MICRO_TARGET = 0x4000_2340
AHEAD_TARGET = PC  # Self-loop sustains S3 fastTrain while MicroBTB is disabled.
LIMIT = 128


@pytest.mark.feature("BPU-INT-016")
async def test_micro_btb_retains_target_during_ahead_btb_learning(bpu_agent):
    coverage = bpu_early_source_isolation_coverage_model()
    await bpu_agent.reset(PC)
    await bpu_agent.configure_predictors(abtb=False, ittage=False)
    cold = await bpu_agent.next_transaction(start_pc=PC)
    assert cold.prediction.taken == 0

    await bpu_agent.train(
        BpuTraining(PC, POSITION, MICRO_TARGET, cold.meta.resolve, branch_type=3)
    )
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    micro_initial_tx = await bpu_agent.next_transaction(
        start_pc=PC, require_taken=True, after_tick=boundary, limit=LIMIT
    )
    micro_initial = micro_initial_tx.prediction
    assert (micro_initial.taken, micro_initial.target, micro_initial.position) == (
        1, MICRO_TARGET, POSITION
    )
    assert micro_initial_tx.meta.perf.s1_source is BpuStage1Source.UBTB
    coverage.sample({"configuration": "micro_initial"})

    # Keep MicroBTB disabled for the MainBTB update and ABTB fastTrain phase.
    await bpu_agent.redirect_and_settle(BpuRedirect(QUIET_PC, cold.meta.redirect))
    await bpu_agent.configure_predictors(ubtb=False)
    await bpu_agent.train(
        BpuTraining(PC, POSITION, AHEAD_TARGET, cold.meta.resolve, branch_type=3)
    )
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    _, repair = await bpu_agent.next_prediction(
        start_pc=PC, target=AHEAD_TARGET, stage="s2", after_tick=boundary,
        limit=LIMIT,
    )
    assert (repair.taken, repair.position) == (1, POSITION)
    await bpu_agent.configure_predictors(abtb=True)
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    _, repair = await bpu_agent.next_prediction(
        start_pc=PC, target=AHEAD_TARGET, stage="s2", after_tick=boundary,
        limit=LIMIT,
    )
    assert repair.taken == 1
    await bpu_agent.pause_prediction_reads()

    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    ahead_only_tx = await bpu_agent.next_transaction(
        start_pc=PC, require_taken=True, after_tick=boundary, limit=LIMIT
    )
    ahead_only = ahead_only_tx.prediction
    assert (ahead_only.taken, ahead_only.target, ahead_only.position) == (
        1, AHEAD_TARGET, POSITION
    )
    assert ahead_only_tx.meta.perf.s1_source is BpuStage1Source.ABTB
    coverage.sample({"configuration": "ahead_only"})

    # Disable AheadBTB and MainBTB before re-enabling MicroBTB. The old
    # MicroBTB target must survive all intervening B-target fastTrain traffic.
    await bpu_agent.redirect_and_settle(BpuRedirect(QUIET_PC, cold.meta.redirect))
    await bpu_agent.configure_predictors(abtb=False, mbtb=False)
    await bpu_agent.redirect_and_settle(BpuRedirect(QUIET_PC, cold.meta.redirect))
    await bpu_agent.configure_predictors(ubtb=True)
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    micro_retained_tx = await bpu_agent.next_transaction(
        start_pc=PC, require_taken=True, after_tick=boundary, limit=LIMIT
    )
    micro_retained = micro_retained_tx.prediction
    assert (micro_retained.taken, micro_retained.target, micro_retained.position) == (
        1, MICRO_TARGET, POSITION
    )
    assert micro_retained_tx.meta.perf.s1_source is BpuStage1Source.UBTB
    coverage.sample({"configuration": "micro_retained"})
    assert MICRO_TARGET != AHEAD_TARGET
    coverage.assert_coverage(100.0)
    write_bpu_early_source_isolation_coverage(coverage, REPO_ROOT)
