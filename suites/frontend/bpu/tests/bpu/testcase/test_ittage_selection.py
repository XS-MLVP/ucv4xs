"""Integrated ITTAGE target selection must outrank a different MainBTB target."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.coverage.catalog import bpu_ittage_selection_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_ittage_selection_coverage
from suites.frontend.bpu.bpu.checker.assertions import mbtb_meta_for_position
from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect
from suites.frontend.bpu.runtime.paths import REPO_ROOT


PC = 0x4000_0800
POSITION = 4
ITTAGE_TARGET = 0x4000_2000
MAIN_BTB_TARGET = 0x4000_4000


def feedback(resolve_meta, target):
    return BpuBatchTraining(
        PC,
        resolve_meta,
        (BpuBranchFeedback(
            POSITION, target, branch_type=3, taken=1, mispredict=1,
        ),),
    )


@pytest.mark.feature("BPU-INT-032")
async def test_ittage_s3_target_overrides_distinct_main_btb_target(bpu_agent):
    coverage = bpu_ittage_selection_coverage_model()
    await bpu_agent.reset(PC)
    initial = await bpu_agent.next_transaction(start_pc=PC)
    await bpu_agent.configure_predictors(
        ubtb=False, abtb=False, tage=False, sc=False,
        ras=False, ittage=True, mbtb=True, settle=True,
    )
    cold = await revisit_from_redirect(bpu_agent, PC, initial.meta.redirect)
    assert cold.prediction.taken == 0
    assert cold.meta.resolve["ittage"]["allocate"]["valid"] == 1

    await bpu_agent.train_batch_with_prediction_pause(
        feedback(cold.meta.resolve, ITTAGE_TARGET)
    )
    resident = await revisit_from_redirect(bpu_agent, PC, cold.meta.redirect)
    assert mbtb_meta_for_position(resident, POSITION)[1]["rawHit"] == 1
    assert resident.meta.resolve["ittage"]["provider"]["valid"] == 1
    coverage.sample({"phase": "provider_resident"})

    await bpu_agent.configure_predictors(ittage=False, settle=True)
    before_update = await revisit_from_redirect(
        bpu_agent, PC, cold.meta.redirect
    )
    await bpu_agent.train_batch_with_prediction_pause(
        feedback(before_update.meta.resolve, MAIN_BTB_TARGET)
    )
    disabled = await revisit_from_redirect(bpu_agent, PC, cold.meta.redirect)
    assert disabled.meta.resolve["ittage"]["provider"]["valid"] == 0
    fallback = await bpu_agent.correction_for(
        disabled, target=MAIN_BTB_TARGET
    )
    assert fallback is not None
    assert (fallback.taken, fallback.position, fallback.target) == (
        1, POSITION, MAIN_BTB_TARGET,
    )
    assert (fallback.s2_override, fallback.s3_override) == (1, 0)
    assert await bpu_agent.correction_for(
        disabled, target=ITTAGE_TARGET
    ) is None
    coverage.sample({"phase": "mbtb_only_target"})

    await bpu_agent.configure_predictors(ittage=True, settle=True)
    selected = await revisit_from_redirect(bpu_agent, PC, cold.meta.redirect)
    assert selected.meta.resolve["ittage"]["provider"]["valid"] == 1
    stage2 = await bpu_agent.correction_for(
        selected, target=MAIN_BTB_TARGET
    )
    assert stage2 is not None
    assert (stage2.taken, stage2.position, stage2.target) == (
        1, POSITION, MAIN_BTB_TARGET,
    )
    assert (stage2.s2_override, stage2.s3_override) == (1, 0)
    coverage.sample({"phase": "s2_mbtb_target"})
    corrected = await bpu_agent.correction_for(
        selected, target=ITTAGE_TARGET
    )
    assert corrected is not None
    assert (corrected.taken, corrected.position, corrected.target) == (
        1, POSITION, ITTAGE_TARGET,
    )
    assert (corrected.s2_override, corrected.s3_override) == (0, 1)
    coverage.sample({"phase": "s3_ittage_target"})

    coverage.assert_coverage(100.0)
    write_bpu_ittage_selection_coverage(coverage, REPO_ROOT)
