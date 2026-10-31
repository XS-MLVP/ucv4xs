"""An ABTB return-path wrap must be repaired by the full MainBTB target."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.transaction.types import BpuStage1Source
from suites.frontend.bpu.bpu.transaction.types import BpuTraining
from suites.frontend.bpu.bpu.coverage.catalog import bpu_abtb_wrap_coverage_model
from suites.frontend.bpu.bpu.coverage.catalog import write_bpu_abtb_wrap_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT


PC = 0x407F_FFE0
TARGET = 0x4080_0100
WRAPPED_RETURN = 0x40BF_FFE0
POSITION = 4
LIMIT = 128


class MissingAbtbHighTargetRepair(AssertionError):
    """The expected full-target correction is absent after a proven wrap."""


@pytest.mark.feature("BPU-INT-018")
@pytest.mark.rtl_defect
@pytest.mark.xfail(
    strict=True,
    raises=MissingAbtbHighTargetRepair,
    reason="BPU S3 compares only target low bits after an ABTB high-bit wrap",
)
async def test_abtb_cross_region_return_target_is_repaired(bpu_agent):
    coverage = bpu_abtb_wrap_coverage_model()
    assert (TARGET >> 22) != (PC >> 22)
    assert (WRAPPED_RETURN & ((1 << 22) - 1)) == (PC & ((1 << 22) - 1))
    assert WRAPPED_RETURN != PC

    await bpu_agent.reset(PC)
    initial = await bpu_agent.next_transaction(start_pc=PC)
    await bpu_agent.configure_predictors(ubtb=False, abtb=False, ittage=False)
    boundary = await bpu_agent.redirect(BpuRedirect(PC, initial.meta.redirect))
    cold_pc = await bpu_agent.next_transaction(start_pc=PC, after_tick=boundary)
    assert cold_pc.prediction.taken == 0
    await bpu_agent.train(
        BpuTraining(PC, POSITION, TARGET, cold_pc.meta.resolve, branch_type=3)
    )
    boundary = await bpu_agent.redirect(BpuRedirect(TARGET, cold_pc.meta.redirect))
    cold_target = await bpu_agent.next_transaction(
        start_pc=TARGET, after_tick=boundary
    )
    assert cold_target.prediction.taken == 0
    await bpu_agent.train(
        BpuTraining(TARGET, POSITION, PC, cold_target.meta.resolve, branch_type=3)
    )

    # Both full-target MainBTB directions must work before testing ABTB.
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold_pc.meta.redirect))
    _, forward = await bpu_agent.next_prediction(
        start_pc=PC, target=TARGET, stage="s2", after_tick=boundary,
        limit=LIMIT,
    )
    assert (forward.taken, forward.position) == (1, POSITION)
    coverage.sample({"phase": "main_forward_full"})
    boundary = await bpu_agent.redirect(BpuRedirect(TARGET, cold_target.meta.redirect))
    _, backward = await bpu_agent.next_prediction(
        start_pc=TARGET, target=PC, stage="s2", after_tick=boundary,
        limit=LIMIT,
    )
    assert (backward.taken, backward.position) == (1, POSITION)
    coverage.sample({"phase": "main_return_full"})

    # The two branches form a natural recurrent stream. ABTB fastTrain learns
    # the return entry; pausing S0 reads lets its read-priority SRAM write land.
    await bpu_agent.configure_predictors(abtb=True)
    boundary = await bpu_agent.redirect(BpuRedirect(PC, cold_pc.meta.redirect))
    await bpu_agent.next_prediction(
        start_pc=PC, target=TARGET, stage="s2", after_tick=boundary,
        limit=LIMIT,
    )
    await bpu_agent.next_prediction(
        start_pc=TARGET, target=PC, stage="s2", after_tick=boundary,
        limit=LIMIT,
    )
    await bpu_agent.pause_prediction_reads(cycles=24)
    wrapped = await bpu_agent.next_transaction(
        start_pc=TARGET, require_taken=True,
        after_tick=boundary, limit=512,
    )
    if (
        wrapped.prediction.target != WRAPPED_RETURN
        or wrapped.prediction.position != POSITION
        or wrapped.prediction.s2_override
        or wrapped.prediction.s3_override
    ):
        raise RuntimeError(f"ABTB wrap antecedent was not established: {wrapped.prediction!r}")
    coverage.sample({"phase": "ahead_return_wrapped"})
    if (
        wrapped.meta.perf.s1_source is not BpuStage1Source.ABTB
        or wrapped.meta.perf.start_pc != TARGET
        or wrapped.meta.perf.s1_target != WRAPPED_RETURN
    ):
        raise RuntimeError(f"ABTB source antecedent was not established: {wrapped.meta.perf!r}")
    coverage.sample({"phase": "ahead_source_echo"})

    corrected = await bpu_agent.correction_for(wrapped, target=PC)
    if corrected is None:
        write_bpu_abtb_wrap_coverage(coverage, REPO_ROOT)
        raise MissingAbtbHighTargetRepair(
            f"ABTB returned {WRAPPED_RETURN:#x} for {TARGET:#x}; "
            f"MainBTB returned full target {PC:#x}, but S2/S3 did not repair it"
        )
    coverage.sample({"phase": "later_full_target"})
    write_bpu_abtb_wrap_coverage(coverage, REPO_ROOT)
