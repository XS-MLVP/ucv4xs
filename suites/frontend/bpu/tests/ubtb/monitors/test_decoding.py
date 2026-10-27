"""The native prediction bundle is decoded into an immutable transaction."""

from __future__ import annotations

from bpuverify.ubtb.transaction.types import UbtbPrediction
from bpuverify.ubtb.checker.assertions import train_taken
from bpuverify.ubtb.case.definitions import DIRECT


async def test_prediction_monitor_decodes_every_architectural_field(ubtb_agent):
    await ubtb_agent.reset()
    await train_taken(ubtb_agent, DIRECT)

    prediction = await ubtb_agent.predict(DIRECT.pc)

    assert prediction == UbtbPrediction(
        valid=1,
        taken=1,
        target=DIRECT.target,
        position=DIRECT.position,
        branch_type=DIRECT.branch_type,
    )
