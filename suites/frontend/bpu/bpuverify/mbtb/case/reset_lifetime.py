"""Complete old-execution reset and new-execution learning intent."""
from bpuverify.mbtb.env.reset_lifetime import ResetLifetime


async def check_reset_lifetime(agent, program, coverage, evidence):
    await ResetLifetime(agent, program, coverage, evidence).run()
