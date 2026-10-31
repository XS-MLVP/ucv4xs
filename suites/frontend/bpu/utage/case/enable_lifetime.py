"""Qualification/disable intent; the environment owns concurrent drivers."""
from suites.frontend.bpu.utage.env.enable_lifetime import EnableLifetime


async def check_enable_lifetime(agent, program, coverage, evidence):
    await EnableLifetime(agent, program, coverage, evidence).run()
