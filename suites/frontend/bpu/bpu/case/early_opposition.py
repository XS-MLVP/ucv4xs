"""A real history alias biases the base without rewriting the protected key."""
from suites.frontend.bpu.bpu.case.early_direction import discover_negative_path
from suites.frontend.bpu.bpu.checker.early_opposition import EarlyOppositionChecks
from suites.frontend.bpu.bpu.env.early_direction import early_direction_program
from suites.frontend.bpu.bpu.env.early_opposition import EarlyOppositionProgram
from suites.frontend.bpu.bpu.model.early_opposition import PC


async def check_early_opposition(agent,coverage):
    checks=EarlyOppositionChecks(coverage,PC)
    async with early_direction_program(agent,PC,checks,program_type=EarlyOppositionProgram) as env:
        await exercise_negative_opposition(env,checks)
        checks.finish_opposition(env.owners)


async def exercise_negative_opposition(env,checks):
    negative=await discover_negative_path(env,checks)
    negative=await env.strong_negative(negative)
    checks.strong_negative(negative)
    positive=await env.steer_main(negative,3)
    positive=await env.positive_base(positive,checks.protected)
    checks.positive_base(positive)
    prepared=await env.steer_main(positive,0)
    checks.main_negative(prepared)
    return await env.opposed(prepared,checks)
