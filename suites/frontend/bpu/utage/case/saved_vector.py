"""Restore one whole vector, not an independently selected age per branch."""
from suites.frontend.bpu.utage.env.saved_vector import run


async def check_saved_vector(agent,program,coverage,evidence):
    await run(agent,program,coverage,evidence)
