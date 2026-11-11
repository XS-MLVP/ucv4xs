"""Long priority first, then retained short learning under another older path."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.early_opposition import exercise_negative_opposition
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.early_direction import early_direction_program
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.short_revisit import Program
from suites.frontend.bpu.testbenches.bpu.checker.short_revisit import Checks


async def run(agent,profile,coverage,evidence):
    checks=Checks(coverage,profile)
    try:
        async with early_direction_program(agent,checks.pc,checks,program_type=Program) as env:
            source=await exercise_negative_opposition(env,checks)
            await env.confirmed_reward(source)
            await env.contradict(source)
            source=await env.consume_long()
            source=await env.prepare_path(source)
            await env.consume_short(source)
            checks.finish_opposition(env.owners)
    finally: evidence.update(checks.snapshot())
