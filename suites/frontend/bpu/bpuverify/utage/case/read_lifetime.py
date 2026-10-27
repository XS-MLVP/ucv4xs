"""A read meets branch-version learning, or follows its completed effect."""
from bpuverify.utage.env.read_lifetime import ReadLifetime


async def check_read_version(agent,program,coverage,evidence):
    await ReadLifetime(agent,program,coverage,evidence).run()


async def check_late_replacement(agent,program,coverage,evidence):
    from bpuverify.utage.env.read_lifetime import run_late_replacement
    await run_late_replacement(agent,program,coverage,evidence)
