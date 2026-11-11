"""Submit intent, then require every service and both history consumers."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.directions import direction_program
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.dual_retirement import DualRetirementProgram
from suites.frontend.bpu.testbenches.bpu.checker.dual_retirement import DualRetirementChecks
from suites.frontend.bpu.testbenches.bpu.model.tage.dual_retirement import PC


async def check_dual_retirement(agent, coverage):
    async with direction_program(agent, PC) as env:
        checks = DualRetirementChecks(env.checker, coverage)
        program = DualRetirementProgram(env, checks)
        await program.prepare()
        async with program.observe():
            await program.replay()
            for name, source in (await program.profile()).items():
                checks.consumed(name, source)
            checks.finish()
