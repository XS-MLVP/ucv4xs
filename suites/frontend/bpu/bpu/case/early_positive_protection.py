"""Taken-source strength and protection are independent semantic obligations."""
from suites.frontend.bpu.bpu.case.early_opposition import exercise_negative_opposition
from suites.frontend.bpu.bpu.checker.early_positive_protection import EarlyPositiveProtectionChecks
from suites.frontend.bpu.bpu.env.early_positive_protection import early_positive_protection_program
from suites.frontend.bpu.bpu.model.early_opposition import PC
from suites.frontend.bpu.bpu.model.early_positive_protection import OLDER_PATHS


async def check_early_positive_protection(agent, mode, coverage):
    checks = EarlyPositiveProtectionChecks(coverage, mode, PC)
    async with early_positive_protection_program(agent, checks) as env:
        source = await exercise_negative_opposition(env, checks)
        checks.protect_seed()
        source = await env.negative_base(source)
        checks.negative_base_source(source)
        source = await env.steer_main(source, 3)
        checks.main_positive(source); checks.arm_seed()
        source = await env.base_bias(source, taken=True)
        if mode != 'direction-return':
            for _ in range(3):  # Three real consistent sources, not waiting cycles: direction4→7.
                source = await env.original_taken(source)
        if mode in ('upper-hold', 'upper-release'):
            for edge in ('approach-upper', 'reach-upper', 'upper-hold'):
                source = await env.base_bias(source, taken=False)
                source = await env.steer_main(source, 3)
                source = await env.original_taken(source)
                await env.wait_edge(checks, edge)
            if mode == 'upper-release':
                source = await env.steer_main(source, 0)
                source = await env.original_taken(source, older=OLDER_PATHS[1])
                await env.wait_edge(checks, 'upper-release')
        elif mode == 'lower-recover':
            source = await env.steer_main(source, 0)
            for path, edge in zip(OLDER_PATHS, ('reach-lower', 'lower-hold'), strict=True):
                source = await env.original_taken(source, older=path)
                await env.wait_edge(checks, edge)
            source = await env.steer_main(source, 3)
            source = await env.original_taken(source)
            await env.wait_edge(checks, 'lower-recover')
        else:
            source = await env.steer_main(source, 0)
            source = await env.original_taken(source, older=OLDER_PATHS[0])
            await env.wait_edge(checks, 'T-becomes-NT')
            source = await env.steer_main(source, 3)
            source = await env.restore_taken_direction(source)
            await env.wait_edge(checks, 'NT-error-restores-T')
            source = await env.base_bias(source, taken=False)
            source = await env.steer_main(source, 3)
            source = await env.original_taken(source)
            await env.wait_edge(checks, 'T-correction-restores-protection')
        if mode in ('upper-release', 'lower-recover'):
            source = await env.steer_main(source, 0)
            source = await env.allocated_not_taken(source)
        source = await env.steer_main(source, 3)
        source = await env.original_taken(source)
        checks.fresh_consumer(source)
        await env.settled(checks)
        checks.finish_boundaries(env.owners)
