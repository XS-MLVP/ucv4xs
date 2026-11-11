"""One complete semantic program through the domain environment."""
from suites.frontend.bpu.testbenches.utage.tests.scenarios.lifetimes.dual_source import run


async def check_dual_source(agent, program, coverage, evidence):
    await run(agent,program,coverage,evidence)
