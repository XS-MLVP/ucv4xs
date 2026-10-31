"""The original longest T provider keeps learning when no longer table exists."""
from suites.frontend.bpu.bpu.case.early_opposition import exercise_negative_opposition
from suites.frontend.bpu.bpu.checker.early_long_positive_protection import EarlyLongPositiveProtectionChecks
from suites.frontend.bpu.bpu.env.early_long_positive_protection import early_long_positive_protection_program
from suites.frontend.bpu.bpu.model.early_opposition import PC


async def check_early_long_positive_protection(agent, mode, coverage):
    checks = EarlyLongPositiveProtectionChecks(coverage, mode, PC)
    async with early_long_positive_protection_program(agent, checks) as env:
        source = await exercise_negative_opposition(env, checks)
        checks.protect_seed()
        source = await env.negative_base(source); checks.negative_base_source(source)
        source = await env.steer_main(source, 3); checks.main_positive(source); checks.arm_seed()
        source = await env.base_bias(source, taken=True)
        for _ in range(3):
            source = await env.original_long(source)
        if mode in ('upper-hold', 'upper-release'):
            for edge in ('reach-upper', 'upper-hold'):
                source = await env.base_bias(source, taken=False)
                source = await env.steer_main(source, 3)
                source = await env.original_long(source)
                await env.wait_edge(checks, edge)
            if mode == 'upper-release':
                source = await env.steer_main(source, 0)
                source = await env.original_long(source, penalty=True)
                await env.wait_edge(checks, 'upper-release')
        elif mode == 'lower-recover':
            source = await env.steer_main(source, 0)
            source = await env.companion_short(source)
            for edge in ('toward-lower', 'reach-lower', 'lower-hold'):
                source = await env.original_long(source, penalty=True)
                await env.wait_edge(checks, edge)
            source = await env.steer_main(source, 3)
            source = await env.companion_short(source, preserve=True)
            source = await env.original_long(source)
            await env.wait_edge(checks, 'lower-recover')
        else:
            source = await env.steer_main(source, 0)
            source = await env.companion_short(source)
            for edge in ('toward-lower', 'reach-lower', 'lower-hold', 'T-becomes-NT'):
                source = await env.original_long(source, penalty=True)
                await env.wait_edge(checks, edge)
            source = await env.steer_main(source, 3)
            source = await env.original_long(source, penalty=True, expect_taken=False)
            await env.wait_edge(checks, 'NT-error-restores-T')
            source = await env.companion_short(source, preserve=True)
            source = await env.base_bias(source, taken=False)
            source = await env.steer_main(source, 3)
            source = await env.original_long(source)
            await env.wait_edge(checks, 'T-correction-restores-protection')
        source = await env.steer_main(source, 3)
        source = await env.original_long(source)
        checks.fresh_consumer(source)
        await env.settled(checks)
        checks.finish_boundaries(env.owners)
