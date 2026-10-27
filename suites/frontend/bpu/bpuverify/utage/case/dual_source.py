"""One complete semantic program through the domain environment."""
from bpuverify.utage.env.dual_source import run


async def check_dual_source(agent, program, coverage, evidence):
    await run(agent,program,coverage,evidence)
