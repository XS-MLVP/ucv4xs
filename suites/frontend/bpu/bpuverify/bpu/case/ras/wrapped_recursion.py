"""Semantic intent; reusable environment owns timing and observation."""
from bpuverify.bpu.env.ras.wrapped_recursion import check_with_agent


async def check_wrapped_recursion(agent, calls, coverage, evidence):
    await check_with_agent(agent, calls, coverage, evidence)
