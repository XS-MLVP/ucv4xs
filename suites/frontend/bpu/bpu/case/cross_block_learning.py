"""Learn two real edges; resolve B while held or flowing; consume B's new experience."""
from suites.frontend.bpu.bpu.checker.cross_block_learning import Checks
from suites.frontend.bpu.bpu.env.cross_block_learning import Program
from suites.frontend.bpu.bpu.env.early_direction import early_direction_program


async def run(agent,profile,coverage,evidence):
    checks=Checks(coverage,profile)
    try:
        async with early_direction_program(agent,checks.program.a,checks,program_type=Program) as env:
            predecessor=await env.initialize()
            await env.resolve_owned('predecessor',predecessor)
            original=await env.query_successor(predecessor)
            await env.resolve_owned('conditional',original)
            predecessor=await env.consume_early_edge(predecessor,checks.program.a)
            original=await env.consume_early_edge(predecessor,checks.program.b)
            predecessor=await env.fresh_predecessor()
            await env.resolve_owned('not-taken',original)
            fallback=await env.query_successor(predecessor)
            await env.resolve_owned('fallback',fallback)
            predecessor=await env.fresh_predecessor()
            await env.consume_learned(predecessor)
            checks.finish()
    finally: evidence.update(checks.snapshot())
