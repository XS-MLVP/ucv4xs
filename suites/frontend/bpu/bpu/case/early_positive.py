"""Return to an independently learned T source while its shared base stays NT."""
from suites.frontend.bpu.bpu.case.early_opposition import exercise_negative_opposition
from suites.frontend.bpu.bpu.checker.early_positive import EarlyPositiveChecks
from suites.frontend.bpu.bpu.env.early_direction import early_direction_program
from suites.frontend.bpu.bpu.env.early_positive import EarlyPositiveProgram
from suites.frontend.bpu.bpu.model.early_opposition import PC


async def check_early_positive(agent,coverage):
    checks=EarlyPositiveChecks(coverage,PC)
    async with early_direction_program(agent,PC,checks,program_type=EarlyPositiveProgram) as env:
        await exercise_positive_opposition(env,checks)
        checks.finish_positive(env.owners)


async def exercise_positive_opposition(env,checks):
    negative=await exercise_negative_opposition(env,checks)
    checks.protect_seed()
    negative=await env.negative_base(negative,checks)
    checks.negative_base_source(negative)
    prepared=await env.steer_main(negative,3)
    checks.main_positive(prepared)
    return await env.positive_opposed(prepared,checks)
