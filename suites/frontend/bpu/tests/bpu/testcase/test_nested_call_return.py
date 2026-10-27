"""Two nested integrated calls must return to distinct frames in LIFO order."""

from __future__ import annotations

import pytest

from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.coverage.catalog import bpu_nested_ras_coverage_model
from bpuverify.bpu.coverage.catalog import write_bpu_nested_ras_coverage
from bpuverify.bpu.checker.assertions import mbtb_meta_for_position
from bpuverify.bpu.checker.assertions import revisit_from_redirect
from bpuverify.common.env.paths import REPO_ROOT


OUTER_CALL = 0x4000_0800
INNER_CALL = 0x4000_0900
INNER_BODY = 0x4000_0A00
POSITION = 15
INNER_RETURN = INNER_CALL + 16
OUTER_RETURN = OUTER_CALL + 16
WRONG_INNER_STATIC_TARGET = 0x4000_0B00
WRONG_OUTER_STATIC_TARGET = 0x4000_0C00


async def stage_correction(agent, transaction, target, stage):
    prediction = await agent.correction_for(transaction, target=target)
    assert prediction is not None, (transaction, target)
    assert (prediction.taken, prediction.position, prediction.target) == (
        1, POSITION, target,
    )
    assert (prediction.s2_override, prediction.s3_override) == (
        (1, 0) if stage == "s2" else (0, 1)
    )
    return prediction


@pytest.mark.feature("BPU-INT-033")
async def test_nested_calls_return_in_lifo_order_through_bpu(bpu_agent):
    coverage = bpu_nested_ras_coverage_model()
    await bpu_agent.reset(OUTER_CALL)
    initial = await bpu_agent.next_transaction(start_pc=OUTER_CALL)
    await bpu_agent.configure_predictors(
        ubtb=False, abtb=False, tage=False, sc=False,
        ittage=False, ras=False, mbtb=True, settle=True,
    )
    cold_outer = await revisit_from_redirect(
        bpu_agent, OUTER_CALL, initial.meta.redirect
    )
    cases = (
        (OUTER_CALL, INNER_CALL, 2, 2),
        (INNER_CALL, INNER_BODY, 2, 2),
        (INNER_BODY, WRONG_INNER_STATIC_TARGET, 3, 1),
        (INNER_RETURN, WRONG_OUTER_STATIC_TARGET, 3, 1),
    )
    cold = cold_outer
    for index, (pc, target, branch_type, ras_action) in enumerate(cases):
        assert cold.prediction.start_pc == pc
        assert cold.prediction.taken == 0
        await bpu_agent.train(BpuTraining(
            pc, POSITION, target, cold.meta.resolve,
            branch_type=branch_type, ras_action=ras_action,
        ))
        if index + 1 < len(cases):
            cold = await revisit_from_redirect(
                bpu_agent, cases[index + 1][0], cold.meta.redirect
            )

    await bpu_agent.configure_predictors(ras=True, settle=True)
    boundary = await bpu_agent.redirect(
        BpuRedirect(OUTER_CALL, cold_outer.meta.redirect)
    )
    outer = await bpu_agent.next_transaction(
        start_pc=OUTER_CALL, after_tick=boundary
    )
    assert mbtb_meta_for_position(outer, POSITION)[1]["rawHit"] == 1
    await stage_correction(bpu_agent, outer, INNER_CALL, "s2")
    coverage.sample({"phase": "outer_call"})

    inner = await bpu_agent.next_transaction(start_pc=INNER_CALL)
    await stage_correction(bpu_agent, inner, INNER_BODY, "s2")
    coverage.sample({"phase": "inner_call"})

    first_return = await bpu_agent.next_transaction(start_pc=INNER_BODY)
    await stage_correction(
        bpu_agent, first_return, WRONG_INNER_STATIC_TARGET, "s2"
    )
    coverage.sample({"phase": "inner_return_mbtb"})
    await stage_correction(bpu_agent, first_return, INNER_RETURN, "s3")
    coverage.sample({"phase": "inner_return_ras"})

    second_return = await bpu_agent.next_transaction(start_pc=INNER_RETURN)
    await stage_correction(
        bpu_agent, second_return, WRONG_OUTER_STATIC_TARGET, "s2"
    )
    coverage.sample({"phase": "outer_return_mbtb"})
    await stage_correction(bpu_agent, second_return, OUTER_RETURN, "s3")
    assert (
        outer.prediction_tick < inner.prediction_tick
        < first_return.prediction_tick < second_return.prediction_tick
    )
    coverage.sample({"phase": "outer_return_ras"})

    coverage.assert_coverage(100.0)
    write_bpu_nested_ras_coverage(coverage, REPO_ROOT)
