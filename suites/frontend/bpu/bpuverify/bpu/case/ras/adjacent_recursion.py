"""Near-capacity recursive owners retain independent counts and return identity."""
from bpuverify.bpu.env.ras.adjacent_recursion import check_with_agent


async def check_adjacent_recursion(agent,program,coverage,evidence):
    await check_with_agent(agent,program,coverage,evidence)
