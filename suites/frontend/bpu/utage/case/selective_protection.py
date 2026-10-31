"""Semantic scenario entry; timing and observation live in the environment."""
from suites.frontend.bpu.utage.env.selective_protection import run as _run


async def run(agent, program, coverage, evidence):
    await _run(agent, program, coverage, evidence)
