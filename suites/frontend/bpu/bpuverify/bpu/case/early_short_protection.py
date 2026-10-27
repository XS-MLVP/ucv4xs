"""Original short-provider strength remains meaningful when longer paths miss."""
from bpuverify.bpu.case.early_direction import discover_negative_path
from bpuverify.bpu.checker.early_short_protection import EarlyShortProtectionChecks
from bpuverify.bpu.env.early_short_protection import early_short_protection_program
from bpuverify.bpu.model.early_opposition import PC
from bpuverify.bpu.model.early_short_protection import OLDER_PATHS


async def check_early_short_protection(agent, mode, coverage):
    checks = EarlyShortProtectionChecks(coverage, mode, PC)
    async with early_short_protection_program(agent, checks) as env:
        source = await discover_negative_path(env, checks)
        source = await env.strong_negative(source)
        checks.strong_negative(source)
        source = await env.original_short(source)  # Natural neutral guidance establishes counter0.
        source = await env.original_short(source)  # Fresh original short consumer, not the long seed.
        if mode in ('upper-hold', 'upper-release'):
            for edge in ('approach-upper', 'reach-upper', 'upper-hold'):
                source = await env.positive(source)
                source = await env.steer_main(source, 0)
                source = await env.original_short(source)
                await env.wait_edge(checks, edge)
            if mode == 'upper-release':
                source = await env.steer_main(source, 3)
                source = await env.original_short(source, OLDER_PATHS[1])
                await env.wait_edge(checks, 'upper-release')
                source = await env.steer_main(source, 0)
                source = await env.original_short(source, OLDER_PATHS[2])
        else:
            source = await env.positive(source)
            for path, edge in zip(OLDER_PATHS, ('reach-lower', 'lower-hold', 'lower-recover'), strict=True):
                if edge == 'lower-recover':
                    source = await env.steer_main(source, 0)
                source = await env.original_short(source, path)
                await env.wait_edge(checks, edge)
        # The last source accepted before the final learning effect cannot
        # serve as that effect's fresh consumer.
        if mode != 'upper-hold':
            source = await env.allocated_long_consumer(source)
        source = await env.original_short(source, OLDER_PATHS[-1])
        checks.fresh_consumer(source)
        await env.settled(checks)
        checks.finish_boundaries(env.owners)
