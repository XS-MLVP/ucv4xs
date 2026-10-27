"""Same-record complete versions cross blocked, committed and clean states."""
from bpuverify.bpu.env.main_service import main_program,prepare
from bpuverify.bpu.env.main_rewrite import MainRewriteService
from bpuverify.bpu.checker.main_rewrite import MainRewriteChecks
from bpuverify.bpu.model.main_rewrite import PC
from bpuverify.bpu.model.main_service import PCS


async def check_main_rewrite(agent,coverage):
    async with main_program(agent) as env:
        cold,originals=await prepare(env)
        for source in cold:env.checker.retire_source(source.meta_tick)
        sources=tuple([await env.capture_source(PC) for _ in range(2)])
        checks=MainRewriteChecks(env.checker,coverage);checks.arm(sources,originals)
        async with MainRewriteService(env,checks) as service:
            await service.start();await service.submit(sources)
            checks.consumed_old(await service.query(PC))
            await service.release()
            current=await env.capture_source(PC);checks.consumed_new(current)
            await service.reactivate(current)
            checks.consumed_latest(await env.capture_source(PC))
            checks.finish(await env.capture_source(PCS[1]))
