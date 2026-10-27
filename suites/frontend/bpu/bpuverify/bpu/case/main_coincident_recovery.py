"""Complete same-boundary semantics; shared env owns both existing drivers."""
from bpuverify.bpu.env.main_accepted_recovery import run


async def check_coincident_recovery(agent,program,coverage,evidence):
    await run(agent,program,coverage,evidence)
