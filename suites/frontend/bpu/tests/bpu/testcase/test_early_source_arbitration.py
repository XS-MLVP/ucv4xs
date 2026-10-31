"""Same-request priority between distinct, simultaneously valid early sources."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.transaction.types import BpuStage1Source
from suites.frontend.bpu.bpu.transaction.types import BpuTraining
from suites.frontend.bpu.bpu.coverage.catalog import bpu_early_source_arbitration_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_early_source_arbitration_coverage
from suites.frontend.bpu.bpu.case.early_source import check_resumed_arbitration
from suites.frontend.bpu.runtime.paths import REPO_ROOT


PC = 0x4000_0800
QUIET_PC = 0x4001_8000
POSITION = 4
MICRO_TARGET = 0x4000_2340
AHEAD_TARGET = PC
LIMIT = 128


@pytest.mark.feature("BPU-INT-017")
async def test_same_s1_dual_valid_selects_ahead_btb(bpu_agent):
    coverage = bpu_early_source_arbitration_coverage_model()
    await bpu_agent.reset(PC)
    await bpu_agent.configure_predictors(abtb=False, ittage=False)
    cold = await bpu_agent.next_transaction(start_pc=PC)
    assert cold.prediction.taken == 0

    # The old MicroBTB target A is kept while the MainBTB and AheadBTB
    # learn B. A conditional AheadBTB entry also exposes a public valid bit
    # through the associated MicroTAGE resolve metadata.
    await bpu_agent.train(
        BpuTraining(PC, POSITION, MICRO_TARGET, cold.meta.resolve, branch_type=3)
    )
    await bpu_agent.redirect_and_settle(BpuRedirect(QUIET_PC, cold.meta.redirect))
    await bpu_agent.configure_predictors(ubtb=False)
    await bpu_agent.train(
        BpuTraining(PC, POSITION, AHEAD_TARGET, cold.meta.resolve, branch_type=1)
    )
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    _, repaired = await bpu_agent.next_prediction(
        start_pc=PC, target=AHEAD_TARGET, stage="s2", after_tick=boundary,
        limit=LIMIT,
    )
    assert (repaired.taken, repaired.position) == (1, POSITION)
    await bpu_agent.configure_predictors(abtb=True)
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    _, repaired = await bpu_agent.next_prediction(
        start_pc=PC, target=AHEAD_TARGET, stage="s2", after_tick=boundary,
        limit=LIMIT,
    )
    assert repaired.taken == 1
    await bpu_agent.pause_prediction_reads()

    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    ahead_only = await bpu_agent.next_transaction(
        start_pc=PC, require_taken=True, after_tick=boundary, limit=LIMIT
    )
    assert ahead_only.meta.perf.s1_source is BpuStage1Source.ABTB
    assert (ahead_only.prediction.target, ahead_only.prediction.position) == (
        AHEAD_TARGET, POSITION
    )
    assert ahead_only.meta.resolve["utage"]["abtbResult"][0]["valid"] == 1
    coverage.sample({"observation": "ahead_entry_valid"})

    # Enabling MicroBTB during a stall does not retroactively run S0 for the
    # held request. Briefly resume and hold a fresh S1 after both controls
    # have reached the RTL, before S3 fastTrain can rewrite target A to B.
    await bpu_agent.set_ready(prediction=False, meta=True)
    await bpu_agent.configure_predictors(ubtb=True, settle=True)
    dual = await bpu_agent.refresh_stalled_prediction()
    assert dual.valid == 1
    assert (
        dual.prediction.start_pc,
        dual.prediction.target,
        dual.prediction.taken,
        dual.prediction.position,
        dual.prediction.s2_override,
        dual.prediction.s3_override,
    ) == (PC, AHEAD_TARGET, 1, POSITION, 0, 0)
    coverage.sample({"observation": "dual_enabled_ahead_selected"})

    # Keep this S1 request stalled. Disabling AheadBTB and MainBTB only
    # unmasks MicroBTB's retained A; no further S0 request is accepted.
    await bpu_agent.configure_predictors(abtb=False, mbtb=False, settle=True)
    micro = bpu_agent.sample_stalled_prediction()
    assert micro.valid == dual.valid == 1
    assert (
        micro.prediction.start_pc,
        micro.prediction.target,
        micro.prediction.taken,
        micro.prediction.position,
        micro.prediction.s2_override,
        micro.prediction.s3_override,
    ) == (PC, MICRO_TARGET, 1, POSITION, 0, 0)
    assert MICRO_TARGET != AHEAD_TARGET
    coverage.sample({"observation": "same_s1_micro_revealed"})

    # The held request alone does not exercise accepted, overlapping traffic.
    # Check fresh adjacent requests and their actual S3 echo after resumption.
    await check_resumed_arbitration(bpu_agent, pc=PC, target=AHEAD_TARGET, position=POSITION,
        checkpoint=cold.meta.redirect, resolve_meta=cold.meta.resolve, micro_target=MICRO_TARGET)
    coverage.sample({"observation": "resumed_pipeline_ahead_selected"})
    coverage.sample({"observation": "resumed_pipeline_micro_adapts"})
    coverage.sample({"observation": "adjacent_resolve_retargets_micro"})
    coverage.assert_coverage(100.0)
    write_bpu_early_source_arbitration_coverage(coverage, REPO_ROOT)
