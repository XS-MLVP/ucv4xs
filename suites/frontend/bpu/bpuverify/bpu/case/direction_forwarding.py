"""Two independently captured old reads learn on adjacent accepted cycles."""
from bpuverify.bpu.checker.direction_forwarding import DirectionForwardingChecks
from bpuverify.bpu.env.directions import direction_program
from bpuverify.bpu.model.tage.forwarding import PC,resolved_path


async def check_direction_forwarding(agent,coverage):
    async with direction_program(agent,PC) as env:
        checks=DirectionForwardingChecks(env.checker,coverage)
        await env.prepare_direction_pair(checks.prepared)
        sources=(await env.capture_source(PC),await env.capture_source(PC))
        checks.arm(sources)
        checks.accepted_burst(await env.resolve_burst(tuple((source,env.branch_path(resolved_path())) for source in sources)))
        final=await env.capture_source(PC)
        checks.consumed(final)
        checks.accepted_saturated(await env.resolve(final,*env.branch_path(resolved_path())))
        checks.retained(await env.capture_source(PC))
        checks.finish()
