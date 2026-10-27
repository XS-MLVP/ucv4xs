"""Full occupancy, retouch ordering, new identity, actual services and readers."""
from bpuverify.bpu.env.directions import direction_program
from bpuverify.bpu.env.retouch_replacement import prepare_retouch_replacement,RetouchReplacementService
from bpuverify.bpu.model.tage.retouch_replacement import AccessRecencySources
from bpuverify.bpu.model.tage.forwarding import PC
from bpuverify.bpu.checker.retouch_replacement import RetouchReplacementChecks


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
