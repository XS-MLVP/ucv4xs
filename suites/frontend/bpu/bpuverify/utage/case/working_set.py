"""One logical lifetime: admission, retained learning, selective recovery."""
from bpuverify.utage.env.working_set import working_set_env
from bpuverify.utage.model.working_set import PHASES


async def check_working_set(agent, program, coverage):
    async with working_set_env(agent, program, coverage) as env:
        await env.prepare()
        for phase in PHASES:
            await env.phase(phase)
        await env.finish()
