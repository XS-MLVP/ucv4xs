"""Complete original duplicate cleanup/reset/new-learning intent."""
from suites.frontend.bpu.mbtb.env.cleanup_reset import CleanupReset


async def check_cleanup_reset(agent,program,coverage,evidence):
    await CleanupReset(agent,program,coverage,evidence).run()
