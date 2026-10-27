"""One complete semantic program; existing driver/monitor/checker own timing."""
from bpuverify.mbtb.case.entry_keys_scenario import check_case


async def check_two_key_lifetime(agent,program,coverage):
    receipt=await check_case(agent,coverage,**program.sample())
    agent.reference.raise_failure()
    return coverage.finish(receipt)
