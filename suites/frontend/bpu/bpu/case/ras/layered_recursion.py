"""Intent entry for independent recursive layers and a complete return chain."""
from suites.frontend.bpu.bpu.env.ras.layered_recursion import check_with_agent


async def check_layered_recursion(agent, program, coverage, evidence):
    await check_with_agent(agent, program, coverage, evidence)
