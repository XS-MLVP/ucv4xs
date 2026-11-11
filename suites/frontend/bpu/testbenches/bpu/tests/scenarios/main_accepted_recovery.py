"""Intent-only entry point for accepted-learning and prediction recovery."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.main_accepted_recovery import run


async def check_accepted_recovery(agent,program,coverage,evidence):
    await run(agent,program,coverage,evidence)
