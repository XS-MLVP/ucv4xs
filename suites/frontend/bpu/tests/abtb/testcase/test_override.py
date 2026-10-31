"""AheadBTB S2/S3 recovery replays saved predictions against overrideStartPc."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_recovery_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_recovery_coverage
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.abtb.checker.assertions import train_taken
from suites.frontend.bpu.abtb.case.definitions import CONDITIONAL
from suites.frontend.bpu.runtime.paths import REPO_ROOT


async def _check_override(abtb_agent, stage: str, coverage=None) -> None:
    await abtb_agent.reset()
    cold = await abtb_agent.predict(CONDITIONAL.pc)
    assert_miss(cold)
    await train_taken(abtb_agent, CONDITIONAL, cold.meta)
    trained = await abtb_agent.predict(CONDITIONAL.pc)
    assert_vector_hit(trained, CONDITIONAL)

    replayed = await abtb_agent.recover_prediction(
        CONDITIONAL.pc, stage=stage, override_pc=CONDITIONAL.pc
    )
    assert_vector_hit(replayed, CONDITIONAL)
    assert replayed.meta["valid"] == 1
    assert replayed.meta["setIdx"] == trained.meta["setIdx"]
    assert replayed.meta["bankMask"] == trained.meta["bankMask"]
    if coverage is not None:
        coverage.sample({"stage_result": f"{stage}_hit"})

    # Keep the ordinary lookup PC fixed, so only overrideStartPc changes.
    retagged = await abtb_agent.recover_prediction(
        CONDITIONAL.pc, stage=stage, override_pc=CONDITIONAL.pc + 0x20
    )
    assert_miss(retagged)
    assert retagged.meta["valid"] == 1
    if coverage is not None:
        coverage.sample({"stage_result": f"{stage}_miss"})


@pytest.mark.feature("BPU-ABTB-016")
async def test_s2_override_replays_saved_prediction_and_retags_pc(abtb_agent):
    await _check_override(abtb_agent, "s2")


@pytest.mark.feature("BPU-ABTB-017")
async def test_s3_override_replays_saved_prediction_and_retags_pc(abtb_agent):
    await _check_override(abtb_agent, "s3")


async def test_abtb_recovery_coverage_closes_defined_bins(abtb_agent):
    coverage = abtb_recovery_coverage_model()
    for stage in ("s2", "s3"):
        await _check_override(abtb_agent, stage, coverage)
    coverage.assert_coverage(100.0)
    write_abtb_recovery_coverage(coverage, REPO_ROOT)
