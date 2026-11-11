"""Semantic intent; reusable environment owns timing and observation."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.main_dynamic_target import check_with_agent


async def check_main_dynamic_target(agent, program, evidence, coverage):
    await check_with_agent(agent, program, evidence, coverage)
