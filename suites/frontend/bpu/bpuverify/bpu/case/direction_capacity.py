"""Fill retained histories, retouch the first, and check every consumer."""
from bpuverify.bpu.checker.direction_capacity import DirectionCapacityChecks
from bpuverify.bpu.env.directions import direction_program
from bpuverify.bpu.env.direction_service import DirectionService,prepare_service_stream
from bpuverify.bpu.model.tage.forwarding import PC,resolved_path


async def check_direction_capacity(agent,coverage,*,checks_factory=DirectionCapacityChecks,binding_factory=None,evidence=None):
    async with direction_program(agent,PC) as env:
        checks=checks_factory(env.checker,coverage)
        try:
            await env.prepare_direction_pair(checks.prepared)
            for path in checks.program.paths[1:]:await env.prepare_direction_history(path,checks.prepared)
            sources=[]
            for history in checks.program.feedback_order:
                path=checks.program.paths[history]
                sources.append(await env.capture_source(PC) if path is None else await env.capture_via(PC,path))
            await prepare_service_stream(env)
            checks.arm(tuple(sources))
            async with DirectionService(env,checks,binding_factory=binding_factory) as service:
                await service.start_stream()
                await service.submit(tuple((source,env.branch_path(resolved_path())) for source in sources))
                for path in checks.program.paths:checks.old_consumed(await service.query(PC,via=path))
                await service.release()
                for path in checks.program.paths:
                    source=await env.capture_source(PC) if path is None else await env.capture_via(PC,path)
                    checks.new_consumed(source)
                checks.finish()
        finally:
            if evidence is not None:evidence.update(checks.snapshot())
