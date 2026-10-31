"""A non-first table provider must also learn from correct feedback."""
import pytest

from suites.frontend.bpu.ittage.case.definitions import PC
from suites.frontend.bpu.ittage.case.definitions import POSITION
from suites.frontend.bpu.ittage.case.definitions import TARGET_A
from suites.frontend.bpu.ittage.transaction.types import IttageTraining


@pytest.mark.feature('BPU-ITTAGE-003')
async def test_second_table_provider_confidence_increments_on_correct_feedback(
    ittage_agent,
):
    await ittage_agent.reset()
    cold = None
    for _ in range(128):
        candidate = await ittage_agent.predict(PC)
        allocation = candidate.meta['allocate']
        if candidate.hit == 0 and allocation['valid'] == 1 and allocation['bits'] == 1:
            cold = candidate
            break
    assert cold is not None, 'no real second-table allocation opportunity'

    await ittage_agent.train(IttageTraining(PC, POSITION, TARGET_A, cold.meta, 1))
    trained = await ittage_agent.predict(PC)
    assert trained.hit == 1 and trained.target == TARGET_A
    assert trained.meta['provider'] == {'bits': 1, 'valid': 1}, trained
    assert trained.meta['providerCnt_value'] == 2

    await ittage_agent.train(IttageTraining(PC, POSITION, TARGET_A, trained.meta, 0))
    incremented = await ittage_agent.predict(PC)
    assert incremented.hit == 1 and incremented.target == TARGET_A
    assert incremented.meta['provider'] == {'bits': 1, 'valid': 1}, incremented
    assert incremented.meta['providerCnt_value'] == 3, incremented
