"""Intent-only entry point for accepted-learning and prediction recovery."""
from bpuverify.bpu.env.main_accepted_recovery import run


async def check_accepted_recovery(agent,program,coverage,evidence):
    await run(agent,program,coverage,evidence)
