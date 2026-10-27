"""Semantic scenario entry; timing and observation live in the environment."""
from bpuverify.utage.env.query_cohort import run as _run


async def run(agent, program, coverage, evidence):
    await _run(agent, program, coverage, evidence)
