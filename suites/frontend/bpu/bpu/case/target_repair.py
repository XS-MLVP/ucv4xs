"""Establish genuine early/full-target sources; agents own protocol timing."""
from suites.frontend.bpu.bpu.checker.target_repair import check_micro_target_repair
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect, BpuTraining


async def check_micro_target_boundary(agent, *, pc, target, position):
    await agent.reset(pc)
    cold = await agent.next_transaction(start_pc=pc)
    assert cold.prediction.taken == 0, cold.prediction
    await agent.train(BpuTraining(pc, position, target, cold.meta.resolve))

    # Positive control: the later source really knows the full target. A bad
    # preparation cannot be classified as the early-target RTL defect.
    await agent.configure_predictors(ubtb=False, abtb=False)
    boundary = await agent.redirect(BpuRedirect(pc, cold.meta.redirect))
    _, full = await agent.next_prediction(start_pc=pc, stage='s2', after_tick=boundary)
    assert (full.target, full.taken, full.position) == (target, 1, position), full

    await agent.configure_predictors(ubtb=True)
    boundary = await agent.redirect(BpuRedirect(pc, cold.meta.redirect))
    original = await agent.next_transaction(start_pc=pc, require_taken=True, after_tick=boundary)
    repairs = await agent.corrections_for(original)
    check_micro_target_repair(original, repairs, pc=pc, target=target, position=position)
