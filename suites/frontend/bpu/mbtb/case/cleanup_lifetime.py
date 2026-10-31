"""Run a complete existing clear/correction program, then close its obligations."""
from suites.frontend.bpu.mbtb.case.cleanup_overlap_scenario import check_case


async def check_cleanup_lifetime(agent,program,coverage):
    receipt=await check_case(agent,coverage,**program.sample())
    agent.reference.raise_failure()
    return coverage.finish(receipt)
