"""Correct opposition learns usefulness while predictions defer its visibility."""
from suites.frontend.bpu.testbenches.bpu.checker.direction_useful import DirectionUsefulChecks
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.directions import direction_program
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.direction_service import prepare_service_stream
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.direction_useful import DirectionUsefulService
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.direction_useful import prepare_useful_sources
from suites.frontend.bpu.testbenches.bpu.model.tage.forwarding import PC
from suites.frontend.bpu.testbenches.bpu.model.tage.forwarding import resolved_path
from suites.frontend.bpu.testbenches.bpu.model.tage.service import VIA_PC


async def check_direction_useful(agent,coverage):
    async with direction_program(agent,PC) as env:
        checks=DirectionUsefulChecks(env.checker,coverage)
        await prepare_useful_sources(env,checks)
        sources=(await env.capture_source(PC),await env.capture_via(PC,VIA_PC),
            await env.capture_source(PC),await env.capture_via(PC,VIA_PC))
        await prepare_service_stream(env);checks.arm(sources)
        async with DirectionUsefulService(env,checks) as service:
            await service.start_stream()
            await service.submit(tuple((source,env.branch_path(resolved_path())) for source in sources))
            checks.old_consumed(await service.query(PC))
            checks.old_consumed(await service.query(PC,via=VIA_PC))
            await service.release()
            checks.new_consumed(await env.capture_source(PC))
            checks.new_consumed(await env.capture_via(PC,VIA_PC))
            checks.finish()
