"""Submit semantic stack actions; the environment owns driver and observation."""
from bpuverify.ras.env.commit_action import run as _run


async def run(agent,program,coverage,evidence):
    await _run(agent,program,coverage,evidence)
