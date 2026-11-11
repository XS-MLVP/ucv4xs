"""DefaultConfig whole-chip DCE is an explicit transaction boundary."""
import pytest

pytestmark = pytest.mark.selftest


async def test_integrated_prediction_exposes_only_consumed_fields_and_rejects_target_queries(bpu_agent):
    await bpu_agent.reset(0x4000_0800)
    _, prediction = await bpu_agent.next_prediction(start_pc=0x4000_0800)
    assert prediction.target is None
    assert not bpu_agent.ports.prediction_target_observable
    with pytest.raises(RuntimeError, match='target.*not observable'):
        await bpu_agent.next_prediction(start_pc=0x4000_0800, target=0x4000_0800)


async def test_integrated_metadata_and_ready_are_valid_only_when_perf_is_dce_removed(bpu_agent):
    await bpu_agent.reset(0x4000_0800)
    meta = await bpu_agent.next_meta()
    assert meta.perf is None and not bpu_agent.ports.meta_perf_observable
    with pytest.raises(ValueError, match='metadata is valid-only'):
        await bpu_agent.set_ready(prediction=True, meta=False)
