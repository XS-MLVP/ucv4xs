from __future__ import annotations

import pytest

from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.checker.assertions import train_direct_branch
from bpuverify.bpu.case.definitions import PC
from bpuverify.bpu.case.definitions import PREDICTION_LIMIT


@pytest.mark.feature("BPU-INT-005")
async def test_redirect_restarts_requested_pc(bpu_agent):
    await bpu_agent.reset(PC)
    meta, _ = await train_direct_branch(bpu_agent)
    await bpu_agent.redirect(BpuRedirect(PC, meta.redirect))
    _, prediction = await bpu_agent.next_prediction(
        start_pc=PC,
        limit=PREDICTION_LIMIT,
    )
    assert prediction.start_pc == PC


@pytest.mark.feature("BPU-INT-006")
async def test_global_disable_suppresses_trained_taken_prediction(bpu_agent):
    await bpu_agent.reset(PC)
    meta, _ = await train_direct_branch(bpu_agent)
    await bpu_agent.set_enabled(False)
    await bpu_agent.redirect(BpuRedirect(PC, meta.redirect))
    _, prediction = await bpu_agent.next_prediction(
        start_pc=PC,
        limit=PREDICTION_LIMIT,
    )
    assert prediction.taken == 0
