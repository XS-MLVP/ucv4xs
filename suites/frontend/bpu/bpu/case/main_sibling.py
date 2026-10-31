"""Semantic intent; reusable environment owns timing and observation."""
from suites.frontend.bpu.bpu.env.main_sibling import check_with_agent


async def check_main_sibling(agent, program, evidence, coverage):
    await check_with_agent(agent, program, evidence, coverage)
