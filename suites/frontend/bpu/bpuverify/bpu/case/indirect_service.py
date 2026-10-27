"""Four original target contexts survive read pressure and become newly visible."""
from bpuverify.bpu.checker.indirect_service import IndirectServiceChecks
from bpuverify.bpu.env.indirect_learning import indirect_program
from bpuverify.bpu.env.indirect_service import IndirectService,prepare_targets,prepare_stream
from bpuverify.bpu.model.ittage_service import PC,PATHS


async def check_indirect_service(agent,coverage,table):
    async with indirect_program(agent,PC) as env:
        await prepare_targets(env,table)
        sources=tuple([await env.capture_path(PC,path) for path in PATHS])
        await prepare_stream(env)
        checks=IndirectServiceChecks(env.checker,coverage,table);checks.arm(sources)
        async with IndirectService(env,checks) as service:
            await service.start();await service.submit(sources)
            for index,path in enumerate(PATHS):checks.consumed(await service.query_path(path),index,committed=False)
            await service.release()
            for index,path in enumerate(PATHS):checks.consumed(await env.capture_path(PC,path),index,committed=True)
            checks.finish()
