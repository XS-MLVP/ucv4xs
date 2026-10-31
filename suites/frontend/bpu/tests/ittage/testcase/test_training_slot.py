"""ITTAGE must select the only valid indirect branch beyond slot zero."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ittage.transaction.types import IttageTraining
from suites.frontend.bpu.ittage.case.definitions import PC
from suites.frontend.bpu.ittage.case.definitions import POSITION


@pytest.mark.feature("BPU-ITTAGE-010")
async def test_later_training_branch_selects_its_target(ittage_agent):
    await ittage_agent.reset()
    cold = await ittage_agent.predict(PC)
    assert cold.hit == 0 and cold.meta["allocate"]["valid"] == 1

    target = 0x4080_1234
    await ittage_agent.train(
        IttageTraining(PC, POSITION, target, cold.meta, 1, branch_index=4)
    )
    trained = await ittage_agent.predict(PC)
    assert trained.hit == 1 and trained.target == target


async def test_training_rejects_invalid_branch_slot(ittage_agent):
    await ittage_agent.reset()
    cold = await ittage_agent.predict(PC)
    with pytest.raises(ValueError, match="branch_index"):
        await ittage_agent.train(
            IttageTraining(PC, POSITION, 0x4080_1234, cold.meta, 1, branch_index=8)
        )
