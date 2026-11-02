"""Discover a real conditional path, then learn an earlier not-taken correction."""
from suites.frontend.bpu.bpu.env.early_direction import early_direction_program
from suites.frontend.bpu.bpu.checker.early_direction_learning import EarlyDirectionChecks
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback


async def check_early_direction(agent,pc,coverage):
    checks=EarlyDirectionChecks(coverage,pc)
    async with early_direction_program(agent,pc,checks) as env:
        await discover_negative_path(env,checks)
        checks.finish()


async def discover_negative_path(env,checks):
    """One normal branch program, reused without moving timing into cases."""
    pc=env.pc
    cold=await env.capture_source(pc)
    event=await env.resolve(cold,BpuBranchFeedback(env.conditional_position,pc,1,taken=1,mispredict=1),retire=False)
    checks.accepted(cold,event,'cold')
    original=await env.seed_ahead(cold)
    checks.ahead_consumer(original)
    if getattr(checks,'requires_short_initialization',False):
        # Original-short obligations need a short-only learning precondition,
        # not the generic continuous program whose stale no-hit S3s can also
        # allocate table1 on DefaultConfig's5/9 histories.
        await env.prepare_short_initialization()
    event=await env.resolve(original,BpuBranchFeedback(env.conditional_position,pc,1,taken=0,mispredict=1),retire=False)
    checks.accepted(original,event,'not-taken')
    # A later branch is a discovery from a NEW source, not an invented record
    # beyond the earlier first misprediction in the same FTQ batch.
    fallback=await env.query(original)
    event=await env.resolve(fallback,BpuBranchFeedback(env.fallback_position,pc,2,taken=1,mispredict=1),retire=False)
    checks.accepted(fallback,event,'fallback')
    consumer=(await env.initialize_short_negative(fallback)
              if getattr(checks,'requires_short_initialization',False)
              else await env.consume_negative(fallback))
    try:
        checks.negative_consumer(consumer)
    except Exception as error:
        if getattr(checks,'requires_short_initialization',False):
            error.add_note('Short initialization input receipts (model state, not RTL oracle): '+repr(env.initialization))
        raise
    return consumer
