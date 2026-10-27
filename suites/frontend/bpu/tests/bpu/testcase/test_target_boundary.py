"""Cross-region target reconstruction through MainBTB and integrated BPU."""

from __future__ import annotations

import pytest

from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.coverage.catalog import bpu_target_boundary_coverage_model
from bpuverify.bpu.coverage.catalog import write_bpu_target_boundary_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.bpu.case.target_repair import check_micro_target_boundary
from bpuverify.bpu.checker.target_repair import MissingMicroFullTargetRepair


PC = 0x407F_FFE0
TARGET = 0x4080_0100
DOWN_PC = 0x4080_0000
DOWN_TARGET = 0x407F_FF00
POSITION = 4
LIMIT = 64


async def _train_boundary_branch(agent, pc: int, target: int):
    await agent.reset(pc)
    cold = await agent.next_transaction(start_pc=pc)
    assert cold.prediction.taken == 0
    await agent.train(BpuTraining(pc, POSITION, target, cold.meta.resolve))
    return cold.meta


@pytest.mark.feature("BPU-INT-012")
async def test_main_btb_repairs_cross_region_target_when_early_sources_are_disabled(bpu_agent):
    coverage = bpu_target_boundary_coverage_model()
    for direction, pc, target in (
        ("overflow", PC, TARGET),
        ("underflow", DOWN_PC, DOWN_TARGET),
    ):
        meta = await _train_boundary_branch(bpu_agent, pc, target)
        await bpu_agent.configure_predictors(ubtb=False, abtb=False)
        await bpu_agent.redirect(BpuRedirect(pc, meta.redirect))

        _, early = await bpu_agent.next_prediction(
            start_pc=pc, stage="s1", limit=LIMIT
        )
        assert early.taken == 0
        _, repaired = await bpu_agent.next_prediction(
            start_pc=pc, require_taken=True, stage="s2", limit=LIMIT
        )
        assert repaired.target == target
        assert (repaired.s2_override, repaired.s3_override) == (1, 0)
        coverage.sample({"direction": direction})

    coverage.assert_coverage(100.0)
    write_bpu_target_boundary_coverage(coverage, REPO_ROOT)


@pytest.mark.feature("BPU-INT-013")
@pytest.mark.rtl_defect
@pytest.mark.xfail(
    strict=True,
    raises=MissingMicroFullTargetRepair,
    reason=(
        "BPU S3 compares only MaxBtbTargetWidth low target bits, so an "
        "early MicroBTB high-bit wrap is not repaired by MainBTB"
    ),
)
async def test_early_partial_target_wrap_is_eventually_corrected(bpu_agent):
    await check_micro_target_boundary(bpu_agent, pc=PC, target=TARGET, position=POSITION)
