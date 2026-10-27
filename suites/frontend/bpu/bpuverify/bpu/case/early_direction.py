"""Discover a real conditional path, then learn an earlier not-taken correction."""
from bpuverify.bpu.env.early_direction import early_direction_program
from bpuverify.bpu.checker.early_direction_learning import EarlyDirectionChecks
from bpuverify.bpu.transaction.types import BpuBranchFeedback


async def check_early_direction(agent,pc,coverage):
    checks=EarlyDirectionChecks(coverage,pc)
    async with early_direction_program(agent,pc,checks) as env:
        await discover_negative_path(env,checks)
        checks.finish()


async def discover_negative_path(env,checks):
    """One normal branch program, reused without moving timing into cases."""
    pc=env.pc
    cold=await env.capture_source(pc)
    event=await env.resolve(cold,BpuBranchFeedback(2,pc,1,taken=1,mispredict=1),retire=False)
    checks.accepted(cold,event,'cold')
    original=await env.seed_ahead(cold)
    checks.ahead_consumer(original)
    event=await env.resolve(original,BpuBranchFeedback(2,pc,1,taken=0,mispredict=1),retire=False)
    checks.accepted(original,event,'not-taken')
    # A later branch is a discovery from a NEW source, not an invented record
    # beyond the earlier first misprediction in the same FTQ batch.
    fallback=await env.query(original)
    event=await env.resolve(fallback,BpuBranchFeedback(4,pc,2,taken=1,mispredict=1),retire=False)
    checks.accepted(fallback,event,'fallback')
    consumer=await env.consume_negative(fallback)
    checks.negative_consumer(consumer)
    return consumer
