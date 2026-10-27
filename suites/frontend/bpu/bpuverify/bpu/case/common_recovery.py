"""One real owned recovery closes only after a fresh public consumer."""
from bpuverify.bpu.env.common_recovery import common_recovery_program


async def check_common_recovery(agent, profile, coverage):
    async with common_recovery_program(agent, profile, coverage) as env:
        await env.prepare()
        source = await env.start_profile()
        tick = await env.recover_profile(source)
        await env.consume_profile(after_tick=tick)
        env.common.finish()
