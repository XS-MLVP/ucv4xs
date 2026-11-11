from __future__ import annotations

from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuMeta
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuPrediction
from suites.frontend.bpu.testbenches.bpu.model.vectors import PC


async def test_prediction_and_meta_monitors_decode_domain_objects(bpu_agent):
    await bpu_agent.reset(PC)
    _, prediction = await bpu_agent.next_prediction(start_pc=PC)
    meta = await bpu_agent.next_meta()
    assert isinstance(prediction, BpuPrediction)
    assert isinstance(meta, BpuMeta)
    assert isinstance(meta.resolve, dict)
    assert isinstance(meta.redirect, dict)
    assert prediction.target is None
    assert meta.perf is None
    assert not bpu_agent.ports.prediction_target_observable
    assert not bpu_agent.ports.meta_perf_observable
