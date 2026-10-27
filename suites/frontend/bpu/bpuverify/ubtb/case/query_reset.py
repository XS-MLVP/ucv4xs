"""Complete old query/reset/new-consumer lifetime intent."""
from bpuverify.ubtb.env.query_reset import QueryResetLifetime


async def check_query_reset_lifetime(agent,program,coverage,evidence):
    await QueryResetLifetime(agent,program,coverage,evidence).run()
