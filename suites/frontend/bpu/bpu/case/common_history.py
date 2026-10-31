"""The same real source distinguishes a completed block from a recovered prefix."""
from suites.frontend.bpu.bpu.env.common_history import common_program,prepare


async def check_common_history(agent,coverage,*,later_conditional,public_only):
    async with common_program(agent,public_only=public_only,coverage=coverage) as env:
        await prepare(env,later_conditional=later_conditional)
        source=await env.start_loop(later_conditional=later_conditional)
        tick=await env.recover_not_taken(source)
        if public_only:await env.consume_recovered_history(later_conditional=later_conditional,after_tick=tick)
        env.common.finish(public_only=public_only)
