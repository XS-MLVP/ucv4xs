"""Same semantic service pattern; one stale-owner qualification is a separate fault."""
from suites.frontend.bpu.bpu.checker.main_service import MainServiceChecks
from suites.frontend.bpu.bpu.env.main_service import main_program,prepare,MainService
from suites.frontend.bpu.bpu.model.main_service import after_earlier_branch


async def check_main_service(agent,coverage,*,stale=False,reclassify=False):
    async with main_program(agent) as env:
        cold,current=await prepare(env);sources=cold[-1:] if stale else current
        checks=MainServiceChecks(env.checker,coverage,stale=stale,reclassify=reclassify);checks.arm(sources,current)
        for source in cold:
            if all(source is not saved for saved in sources):env.checker.retire_source(source.meta_tick)
        async with MainService(env,checks) as service:
            await service.start();await service.submit(sources)
            for i,pc in enumerate(checks.pcs):checks.consumed(await service.query(pc),i,committed=False)
            await service.release()
            for i,pc in enumerate(checks.pcs):checks.consumed(await env.capture_source(pc),i,committed=True)
            if reclassify:
                for i,pc in enumerate(checks.pcs):checks.sibling(await env.capture_source(after_earlier_branch(pc)),i)
            checks.finish()
