"""Complete old-execution reset and new-execution learning intent."""
from suites.frontend.bpu.testbenches.ubtb.tests.scenarios.lifetimes.reset_lifetime import ResetLifetime


async def check_reset_lifetime(agent, program, coverage, evidence):
    await ResetLifetime(agent, program, coverage, evidence).run()
