"""Accept under read pressure, consume old state, release, consume new state."""
from bpuverify.bpu.checker.direction_service import DirectionServiceChecks
from bpuverify.bpu.env.directions import direction_program
from bpuverify.bpu.env.direction_service import DirectionService,prepare_service_stream
from bpuverify.bpu.model.tage.forwarding import PC,resolved_path
from bpuverify.bpu.model.tage.service import VIA_PC


async def check_direction_service(agent,coverage):
    async with direction_program(agent,PC) as env:
        checks=DirectionServiceChecks(env.checker,coverage)
        await env.prepare_direction_pair(checks.prepared)
        await env.prepare_second_history(checks.prepared)
        sources=(await env.capture_source(PC),await env.capture_via(PC,VIA_PC),
            await env.capture_source(PC),await env.capture_via(PC,VIA_PC))
        await prepare_service_stream(env)
        checks.arm(sources)
        async with DirectionService(env,checks) as service:
            await service.start_stream()
            await service.submit(tuple((source,env.branch_path(resolved_path())) for source in sources))
            checks.old_consumed(await service.query(PC))
            checks.old_consumed(await service.query(PC,via=VIA_PC))
            await service.release()
            checks.new_consumed(await env.capture_source(PC))
            checks.new_consumed(await env.capture_via(PC,VIA_PC))
            checks.finish()
