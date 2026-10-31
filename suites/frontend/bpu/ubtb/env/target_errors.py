"""Two independently owned wrong targets must both weaken one live record."""
from dataclasses import replace

from suites.frontend.bpu.ubtb.transaction.types import BranchTraining,UbtbBatchTraining,UbtbBranchFeedback,UbtbPrediction


async def check_adjacent_wrong_targets(agent, second_source):
    if second_source not in ('fast','resolve'):raise ValueError('unknown feedback source')
    original = BranchTraining(0x80090060,0x8014048c,1,7,3)
    first = replace(original,target=original.target-4)
    second = replace(original,target=original.target-8)
    third = replace(original,target=original.target-12)
    expected = UbtbPrediction(1,1,original.target,7,3)
    await agent.reset()
    await agent.train(original)
    assert await agent.predict(original.pc) == expected
    accepted_first = await agent.training_driver.send(first)
    if second_source == 'fast':
        accepted_second = await agent.training_driver.send(second)
    else:
        accepted_second = await agent.resolve_driver.send(UbtbBatchTraining(original.pc,(
            UbtbBranchFeedback(second.target,1,7,3,mispredict=1),)))
    assert accepted_second.tick == accepted_first.tick+2, 'the two distinct errors must be adjacent, not simultaneous arbitration'
    assert await agent.predict(original.pc) == expected, 'two errors weaken but do not yet replace the original target'
    await agent.train(third)
    assert (await agent.predict(original.pc)).valid == 0, 'all three real errors must deplete confidence exactly once each'
