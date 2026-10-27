"""Every legal feedback slot must select its own qualifying indirect branch."""
import pytest

from bpuverify.ittage.case.definitions import PC
from bpuverify.ittage.case.definitions import POSITION
from bpuverify.ittage.transaction.types import IttageTraining


@pytest.mark.feature('BPU-ITTAGE-010')
@pytest.mark.parametrize('branch_index', range(8))
async def test_only_qualifying_branch_in_each_feedback_slot_learns_its_target(
    ittage_agent, branch_index,
):
    await ittage_agent.reset()
    cold = await ittage_agent.predict(PC)
    assert cold.hit == 0
    assert cold.meta['allocate']['valid'] == 1

    target = 0x4080_1234 + 0x20 * branch_index
    await ittage_agent.train(
        IttageTraining(PC, POSITION, target, cold.meta, 1,
                       branch_index=branch_index)
    )
    trained = await ittage_agent.predict(PC)
    assert (trained.hit, trained.target) == (1, target), (branch_index, trained)
