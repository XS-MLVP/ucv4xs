"""Real semantic programs, checked by the agent's default reference."""
import pytest

from suites.frontend.bpu.ittage.case.definitions import PC, POSITION
from suites.frontend.bpu.ittage.case.semantic import CROSS_TARGET, retarget_without_table_allocation
from suites.frontend.bpu.ittage.transaction.types import IttageTraining


@pytest.mark.feature('BPU-ITTAGE-009')
async def test_default_parallel_prediction_preserves_independent_history_snapshots(ittage_agent):
    await ittage_agent.reset()
    contexts = ((0, 0x40002000), (4, 0x40006000), (8, 0x40009000))
    for history, target in contexts:
        cold = await ittage_agent.predict(PC, folded_history=history)
        await ittage_agent.train(IttageTraining(PC, POSITION, target, cold.meta, 1, folded_history=history))
    before = ittage_agent.reference.board.status.checked
    sequence = (*contexts, *reversed(contexts))
    transfers = [ittage_agent.submit_predict(PC, folded_history=history) for history, _ in sequence]
    await ittage_agent.drain_predictions()
    actual = [await transfer for transfer in transfers]
    assert [value.target for value in actual] == [target for _, target in sequence]
    status = ittage_agent.reference.board.status
    assert status.checked >= before + len(transfers) and status.failed == 0


@pytest.mark.feature('BPU-ITTAGE-019')
@pytest.mark.feature('BPU-ITTAGE-017')
@pytest.mark.parametrize('region_resident', [True, False], ids=['existing-region', 'new-region'])
async def test_zero_confidence_retarget_preserves_full_region_without_new_table(ittage_agent, region_resident):
    actual = await retarget_without_table_allocation(ittage_agent, region_resident=region_resident)
    # The alternate may mask the primary's bad target in the architectural
    # prediction. The independent model checks both complete target metadata
    # fields, not only the selected indirect target.
    assert actual.meta['providerTarget_addr'] == CROSS_TARGET
