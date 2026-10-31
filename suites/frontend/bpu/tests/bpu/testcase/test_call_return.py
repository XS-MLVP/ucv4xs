from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.transaction.types import BpuTraining
from suites.frontend.bpu.bpu.case.definitions import PREDICTION_LIMIT


CALL_PC = 0x4000_0800
CALL_POSITION = 4
CALLEE_PC = 0x4000_2000
RETURN_POSITION = 2
WRONG_STATIC_RETURN_TARGET = 0x4000_3800


def return_target(start_pc: int, position: int) -> int:
    return (start_pc & ~0x7) + position + 1


@pytest.mark.feature("BPU-INT-008")
async def test_direct_call_and_indirect_return_cooperate_through_ras(bpu_agent):
    await bpu_agent.reset(CALL_PC)
    cold_call = await bpu_agent.next_transaction(start_pc=CALL_PC)
    await bpu_agent.train(
        BpuTraining(
            CALL_PC,
            CALL_POSITION,
            CALLEE_PC,
            cold_call.meta.resolve,
            branch_type=2,
            ras_action=2,
        )
    )
    await bpu_agent.redirect(BpuRedirect(CALL_PC, cold_call.meta.redirect))
    _, call = await bpu_agent.next_prediction(
        start_pc=CALL_PC,
        require_taken=True,
        limit=PREDICTION_LIMIT,
    )
    assert call.target == CALLEE_PC

    cold_return = await bpu_agent.next_transaction(
        start_pc=CALLEE_PC,
        limit=PREDICTION_LIMIT,
    )
    await bpu_agent.train(
        BpuTraining(
            CALLEE_PC,
            RETURN_POSITION,
            WRONG_STATIC_RETURN_TARGET,
            cold_return.meta.resolve,
            branch_type=3,
            ras_action=1,
        )
    )
    await bpu_agent.redirect(BpuRedirect(CALLEE_PC, cold_return.meta.redirect))
    _, returned = await bpu_agent.next_prediction(
        start_pc=CALLEE_PC,
        require_taken=True,
        stage="s3",
        limit=PREDICTION_LIMIT,
    )

    assert returned.target == return_target(CALL_PC, CALL_POSITION)
    assert returned.target != WRONG_STATIC_RETURN_TARGET
