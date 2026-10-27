"""Four actual branches retain original protection attribution across feedback."""
from bpuverify.utage.env.cross_branch_protection import run


async def check_cross_branch_protection(agent, program, coverage, evidence):
    await run(agent, program, coverage, evidence)
