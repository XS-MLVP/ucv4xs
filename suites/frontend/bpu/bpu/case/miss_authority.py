"""Semantic scenario; environment owns driver, monitor and timing."""
from suites.frontend.bpu.bpu.env.miss_authority import run as _run


async def run(agent, program, coverage, evidence):
    await _run(agent, program, coverage, evidence)
