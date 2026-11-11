"""Complete old query/reset/new-consumer lifetime intent."""
from suites.frontend.bpu.testbenches.ubtb.tests.scenarios.lifetimes.query_reset import QueryResetLifetime


async def check_query_reset_lifetime(agent,program,coverage,evidence):
    await QueryResetLifetime(agent,program,coverage,evidence).run()
