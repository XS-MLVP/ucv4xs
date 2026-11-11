"""Four actual branches retain original protection attribution across feedback."""
from suites.frontend.bpu.testbenches.utage.tests.scenarios.lifetimes.cross_branch_protection import run


async def check_cross_branch_protection(agent, program, coverage, evidence):
    await run(agent, program, coverage, evidence)
