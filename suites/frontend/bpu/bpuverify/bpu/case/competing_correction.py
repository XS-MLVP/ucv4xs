"""A held old lookup versus normal discovery of a younger conditional."""
from bpuverify.bpu.checker.competing_correction import Checks
from bpuverify.bpu.env.competing_correction import competing_program


async def run(agent,profile,coverage,evidence):
    checks=Checks(coverage,profile)
    try:
        async with competing_program(agent,checks) as env:
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
            await env.hold_old_lookup(predecessor)
            await env.resolve_owned('young-discovery',predecessor)
            await env.compete()
            await env.consume_restored()
            checks.finish()
    finally:evidence.update(checks.snapshot())
