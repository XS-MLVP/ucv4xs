"""Intent is resolution order and sibling preservation; environment owns timing."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.main_original_order import run as _run


async def run(agent,program,coverage,evidence):
    await _run(agent,program,coverage,evidence)
