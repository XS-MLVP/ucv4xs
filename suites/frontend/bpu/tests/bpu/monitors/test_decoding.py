from __future__ import annotations

from suites.frontend.bpu.bpu.transaction.types import BpuMeta
from suites.frontend.bpu.bpu.transaction.types import BpuPrediction
from suites.frontend.bpu.bpu.case.definitions import PC


async def test_prediction_and_meta_monitors_decode_domain_objects(bpu_agent):
    await bpu_agent.reset(PC)
    _, prediction = await bpu_agent.next_prediction(start_pc=PC)
    meta = await bpu_agent.next_meta()
    assert isinstance(prediction, BpuPrediction)
    assert isinstance(meta, BpuMeta)
    assert isinstance(meta.resolve, dict)
    assert isinstance(meta.redirect, dict)
