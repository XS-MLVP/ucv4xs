from __future__ import annotations

import pytest

from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.case.definitions import PC
from suites.frontend.bpu.bpu.case.definitions import REDIRECT_PC


@pytest.mark.feature("BPU-INT-010")
async def test_redirect_replaces_stalled_prediction_before_ready_resumes(bpu_agent):
    await bpu_agent.reset(PC)
    cold = await bpu_agent.next_transaction(start_pc=PC)
    observed = await bpu_agent.redirect_while_backpressured(
        BpuRedirect(REDIRECT_PC, cold.meta.redirect)
    )

    state = f"redirect={REDIRECT_PC:#x}, observed={observed!r}"
    assert observed.stalled_valid == 1, state
    assert observed.stalled_prediction.start_pc != REDIRECT_PC, state
    assert observed.redirected_valid == 1, state
    assert observed.redirected_prediction.start_pc == REDIRECT_PC, state
    assert observed.first_accepted_prediction.start_pc == REDIRECT_PC, state
