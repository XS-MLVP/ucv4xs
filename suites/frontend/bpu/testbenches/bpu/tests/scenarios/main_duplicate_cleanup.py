"""Declare branch identities and overlap; environment owns driving."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.main_duplicate_cleanup import run


async def check_duplicate_cleanup(agent,program,coverage,evidence):
    await run(agent,program,coverage,evidence)
