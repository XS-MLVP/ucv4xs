"""Domain-level programs for independent target learning checks."""
from suites.frontend.bpu.ittage.checker.assertions import prepare_null_highest_provider
from suites.frontend.bpu.ittage.case.definitions import PC, POSITION
from suites.frontend.bpu.ittage.transaction.types import IttageTraining


CROSS_TARGET = 0x41001400


async def retarget_without_table_allocation(agent, *, region_resident):
    await agent.reset()
    if region_resident:
        other_pc = PC + 0x40
        cold = await agent.predict(other_pc)
        await agent.train(IttageTraining(other_pc, POSITION, CROSS_TARGET, cold.meta, 1))
        await agent.predict(other_pc)  # Independent model checks the resident too.
    source = await prepare_null_highest_provider(agent, pc=PC, position=POSITION)
    assert source.meta['allocate']['valid'] == 0 and source.meta['providerCnt_value'] == 0
    await agent.train(IttageTraining(PC, POSITION, CROSS_TARGET, source.meta, 1))
    return await agent.predict(PC)
