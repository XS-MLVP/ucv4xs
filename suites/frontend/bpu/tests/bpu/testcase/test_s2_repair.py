"""Integrated S2 prediction repairs a missing early-stage prediction."""

from __future__ import annotations

import pytest

from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.coverage.catalog import bpu_s2_repair_coverage_model
from bpuverify.bpu.coverage.catalog import write_bpu_s2_repair_coverage
from bpuverify.bpu.checker.assertions import train_direct_branch
from bpuverify.bpu.case.definitions import PC
from bpuverify.bpu.case.definitions import PREDICTION_LIMIT
from bpuverify.bpu.case.definitions import TARGET
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-INT-011")
async def test_main_btb_repairs_disabled_s1_predictors_in_s2(bpu_agent):
    await bpu_agent.reset(PC)
    coverage = bpu_s2_repair_coverage_model()
    meta, trained = await train_direct_branch(bpu_agent)
    assert trained.target == TARGET

    # Preserve MainBTB, but remove both early prediction sources. The trained
    # branch should reappear as an S2 correction, not as a stale S1 transfer.
    await bpu_agent.configure_predictors(ubtb=False, abtb=False)
    await bpu_agent.redirect(BpuRedirect(PC, meta.redirect))
    _, early = await bpu_agent.next_prediction(
        start_pc=PC,
        stage="s1",
        limit=PREDICTION_LIMIT * 2,
    )
    assert early.taken == 0
    coverage.sample({"stage": "s1_miss", "taken": early.taken})
    _, repaired = await bpu_agent.next_prediction(
        start_pc=PC,
        require_taken=True,
        stage="s2",
        limit=PREDICTION_LIMIT * 2,
    )
    assert repaired.s2_override == 1
    assert repaired.s3_override == 0
    assert repaired.target == TARGET
    coverage.sample({"stage": "s2_repair", "taken": repaired.taken})
    coverage.assert_coverage(100.0)
    write_bpu_s2_repair_coverage(coverage, REPO_ROOT)
