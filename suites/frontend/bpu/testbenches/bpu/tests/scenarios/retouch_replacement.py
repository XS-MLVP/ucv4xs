"""Full occupancy, retouch ordering, new identity, actual services and readers."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.directions import direction_program
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.retouch_replacement import prepare_retouch_replacement
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.retouch_replacement import RetouchReplacementService
from suites.frontend.bpu.testbenches.bpu.model.tage.retouch_replacement import AccessRecencySources
from suites.frontend.bpu.testbenches.bpu.model.tage.forwarding import PC
from suites.frontend.bpu.testbenches.bpu.checker.retouch_replacement import RetouchReplacementChecks


async def check_retouch_replacement(agent,coverage,program):
    async with direction_program(agent,PC,sources_factory=AccessRecencySources) as env:
        checks=RetouchReplacementChecks(env.checker,coverage,program)
        await prepare_retouch_replacement(env,checks)
        async with RetouchReplacementService(env,checks) as service:
            await service.start_stream();await service.submit_program()
            for path in program.paths:checks.old_consumed(await service.query(PC,via=path))
            await service.release()
            for path in program.paths:
                source=await env.capture_source(PC) if path is None else await env.capture_via(PC,path)
                checks.new_consumed(source)
            checks.finish()
