from __future__ import annotations

import pytest

from bpuverify.bpu.checker.assertions import train_direct_branch
from bpuverify.bpu.case.definitions import TARGET


@pytest.mark.feature("BPU-INT-004")
async def test_ftq_training_changes_later_prediction(bpu_agent):
    await bpu_agent.reset(0x4000_0800)
    _, prediction = await train_direct_branch(bpu_agent)
    assert prediction.taken == 1
    assert prediction.target == TARGET
