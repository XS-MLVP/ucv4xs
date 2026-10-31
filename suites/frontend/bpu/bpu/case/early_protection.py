"""Protection limits and reverse recovery, not physical coordinate coverage."""
from suites.frontend.bpu.bpu.case.early_direction import discover_negative_path
from suites.frontend.bpu.bpu.case.early_opposition import exercise_negative_opposition
from suites.frontend.bpu.bpu.checker.early_protection import EarlyProtectionChecks
from suites.frontend.bpu.bpu.env.early_protection import early_protection_program
from suites.frontend.bpu.bpu.model.early_opposition import PC


async def check_early_protection(agent, mode, coverage):
    checks = EarlyProtectionChecks(coverage, mode, PC)
    async with early_protection_program(agent, checks) as env:
        if mode in ('upper-hold', 'upper-release'):
            source = await exercise_negative_opposition(env, checks)
            source = await env.opposed_again(source, checks)
            await env.wait_edge(checks, 'upper-hold')
            if mode == 'upper-release':
                source = await env.wrong_original(source, checks, 'upper-release')
                source = await env.correct_original(source, checks)
        else:
            source = await discover_negative_path(env, checks)
            source = await env.strong_negative(source)
            checks.strong_negative(source)
            for edge in ('toward-lower', 'reach-lower', 'lower-hold'):
                source = await env.wrong_original(source, checks, edge)
            source = await env.correct_original(source, checks, edge='lower-recover')
        await env.final_consumer(source, checks)
        checks.finish_boundaries(env.owners)
