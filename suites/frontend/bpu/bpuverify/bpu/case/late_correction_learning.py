"""Resolve real paths, teach one original at S3, consume the new direction."""
from bpuverify.bpu.checker.late_correction_learning import Checks
from bpuverify.bpu.env.late_correction_learning import late_correction_program


async def run(agent,profile,coverage,evidence):
    checks=Checks(coverage,profile)
    try:
        async with late_correction_program(agent,checks) as env:
            predecessor=await env.initialize()
            await env.resolve_owned('predecessor',predecessor)
            source=await env.query_successor(predecessor)
            await env.resolve_owned('conditional',source)
            predecessor=await env.seed_early(predecessor)
            await env.early_enabled(False)
            source=await env.query_successor(predecessor)
            await env.resolve_owned('not-taken',source)
            source=await env.query_successor(predecessor)
            await env.resolve_owned('strengthen-negative',source)
            source=await env.query_successor(predecessor)
            await env.resolve_owned('fallback',source)
            predecessor=await env.stable_predecessor(predecessor)
            source=await env.query_successor(predecessor)
            await env.resolve_owned('late-surprise',source)
            await env.weak_control(predecessor)
            await env.early_enabled(True)
            await env.original_teacher(predecessor)
            await env.consume_learned()
            checks.finish()
    finally: evidence.update(checks.snapshot())
