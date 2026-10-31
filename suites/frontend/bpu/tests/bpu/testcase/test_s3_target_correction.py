"""S3 repairs a low-bit target disagreement between MicroBTB and MainBTB."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.transaction.types import BpuTraining
from suites.frontend.bpu.bpu.coverage.catalog import bpu_s3_target_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_s3_target_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT


PC = 0x4000_0800
POSITION = 4
OLD_TARGET = 0x4000_2340
NEW_TARGET = 0x4000_2540
LIMIT = 64


@pytest.mark.feature("BPU-INT-014")
async def test_s3_corrects_main_btb_low_target_disagreement(bpu_agent):
    coverage = bpu_s3_target_coverage_model()
    assert OLD_TARGET >> 22 == NEW_TARGET >> 22
    assert OLD_TARGET != NEW_TARGET

    await bpu_agent.reset(PC)
    cold = await bpu_agent.next_transaction(start_pc=PC)
    assert cold.prediction.taken == 0
    await bpu_agent.train(
        BpuTraining(PC, POSITION, OLD_TARGET, cold.meta.resolve, branch_type=3),
        prediction_pause=True,
    )
    await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    original = await bpu_agent.next_transaction(start_pc=PC, require_taken=True)
    assert original.prediction.target == OLD_TARGET

    # Leave MicroBTB intact while updating the indirect MainBTB entry.
    # Disable ITTAGE so the later target source is unambiguously MainBTB.
    await bpu_agent.configure_predictors(ubtb=False, abtb=False, ittage=False)
    await bpu_agent.redirect(BpuRedirect(PC, original.meta.redirect))
    before_update = await bpu_agent.next_transaction(start_pc=PC)
    assert before_update.prediction.taken == 0
    await bpu_agent.train(
        BpuTraining(PC, POSITION, NEW_TARGET, before_update.meta.resolve,
                    branch_type=3),
        prediction_pause=True,
    )

    await bpu_agent.configure_predictors(ubtb=True)
    await bpu_agent.redirect(BpuRedirect(PC, before_update.meta.redirect))
    _, early = await bpu_agent.next_prediction(
        start_pc=PC, require_taken=True, stage="s1", limit=LIMIT
    )
    assert (early.target, early.position) == (OLD_TARGET, POSITION)
    coverage.sample({"stage_target": "s1_old"})

    _, corrected = await bpu_agent.next_prediction(
        start_pc=PC, require_taken=True, stage="s3", limit=LIMIT
    )
    assert (corrected.target, corrected.position) == (NEW_TARGET, POSITION)
    assert (corrected.s2_override, corrected.s3_override) == (0, 1)
    coverage.sample({"stage_target": "s3_new"})

    coverage.assert_coverage(100.0)
    write_bpu_s3_target_coverage(coverage, REPO_ROOT)
