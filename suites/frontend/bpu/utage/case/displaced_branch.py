"""One readable domain operation; no clock phases or native IO in the case."""
from suites.frontend.bpu.utage.env.displaced_branch import run


async def check_displaced_branch(agent,program,coverage,evidence):
    await run(agent,program,coverage,evidence)
