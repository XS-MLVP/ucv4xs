"""Train after selection has switched from the primary to its alternate."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.testbenches.ittage.transactions.types import IttageTraining
from suites.frontend.bpu.testbenches.ittage.checker.assertions import allocate_below_highest
from suites.frontend.bpu.testbenches.ittage.model.vectors import PC
from suites.frontend.bpu.testbenches.ittage.model.vectors import POSITION
from suites.frontend.bpu.testbenches.ittage.model.vectors import TARGET_A
from suites.frontend.bpu.testbenches.ittage.model.vectors import TARGET_B


@pytest.mark.feature("BPU-ITTAGE-007")
async def test_unconfident_primary_training_keeps_alternate_target(ittage_agent):
    await ittage_agent.reset()
    pc, first = await allocate_below_highest(ittage_agent)
    await ittage_agent.train(IttageTraining(pc, POSITION, TARGET_B, first.meta, 1))
    prediction = await ittage_agent.predict(pc)
    assert prediction.meta["provider"]["valid"] == 1
    assert prediction.meta["altProvider"]["valid"] == 1

    for _ in range(4):
        if prediction.meta["providerCnt_value"] == 0:
            break
        await ittage_agent.train(IttageTraining(pc, POSITION, TARGET_A, prediction.meta, 0))
        prediction = await ittage_agent.predict(pc)

    assert prediction.target == TARGET_A
    assert prediction.meta["providerCnt_value"] == 0
    assert prediction.meta["altProvider"]["valid"] == 1
    alternate_target = prediction.meta["altProviderTarget_addr"]

    # The previous selection test stops here. Training with this metadata also
    # exercises the alternate-target path when the primary counter is zero.
    await ittage_agent.train(IttageTraining(pc, POSITION, TARGET_A, prediction.meta, 0))
    trained = await ittage_agent.predict(pc)
    assert trained.hit == 1
    assert trained.target == TARGET_A
    assert trained.meta["altProviderTarget_addr"] == alternate_target
