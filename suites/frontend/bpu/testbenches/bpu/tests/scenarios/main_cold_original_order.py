"""Semantic intent only; the shared environment owns concurrent lifetime work."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.main_cold_original_order import run as _run


async def run(agent,program,coverage,evidence):
    await _run(agent,program,coverage,evidence)
