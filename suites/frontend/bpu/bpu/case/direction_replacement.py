"""Old key reaches saturation, then full miss; reconsume every history."""
from suites.frontend.bpu.bpu.checker.direction_replacement import DirectionReplacementChecks
from suites.frontend.bpu.bpu.env.directions import direction_program
from suites.frontend.bpu.bpu.env.direction_service import DirectionService,prepare_service_stream
from suites.frontend.bpu.bpu.model.tage.forwarding import PC,resolved_path


async def check_direction_replacement(agent,coverage):
    async with direction_program(agent,PC) as env:
        checks=DirectionReplacementChecks(env.checker,coverage)
        await env.prepare_direction_pair(checks.prepared)
        # Secondary histories share MainBTB, so finish all of them before
        # strengthening A and changing the shared base to 0/3.
        for path in checks.program.paths[1:]:await env.prepare_direction_history(path,checks.prepared)
        source=await env.capture_source(PC)
        await env.resolve(source,*env.branch_path(resolved_path()))
        after=await env.capture_source(PC)
        checks.prepared(after,((0,3),(1,6)))
        env.checker.retire_source(source.meta_tick)
        env.checker.retire_source(after.meta_tick)
        sources=[]
        for path in checks.program.paths:
            sources.append(await env.capture_source(PC) if path is None else await env.capture_via(PC,path))
        await prepare_service_stream(env)
        checks.arm(tuple(sources))
        async with DirectionService(env,checks) as service:
            await service.start_stream()
            await service.submit(tuple((source,env.branch_path(resolved_path())) for source in sources))
            for path in checks.program.paths:checks.old_consumed(await service.query(PC,via=path))
            await service.release()
            for path in checks.program.paths:
                source=await env.capture_source(PC) if path is None else await env.capture_via(PC,path)
                checks.new_consumed(source)
            checks.finish()
