"""Logical learning lifetime; the environment owns timing and observation."""
from bpuverify.utage.env.learning_persistence import run as _run


async def run(agent, program, coverage, evidence):
    await _run(agent, program, coverage, evidence)
