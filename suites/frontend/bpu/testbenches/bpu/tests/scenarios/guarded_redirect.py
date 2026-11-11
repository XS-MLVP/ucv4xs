"""Bounded redirect-wire guard checks plus the PHR consumer projection."""
from suites.frontend.bpu.testbenches.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.testbenches.bpu.env.agent.pipeline import PipelineObservation
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuRedirect


async def check_guarded_redirect(agent, *, guarded):
    pc = 0x40000800
    phr = BpuPhrChecker(scope='guarded redirect wire and PHR unGuard', record_limit=8)
    async with PipelineObservation(agent) as observation, agent.observe_phr(phr) as history:
        await agent.reset(pc)
        source = await agent.next_transaction(start_pc=pc)
        await agent.configure_predictors(ubtb=False, abtb=False, mbtb=False,
            tage=False, sc=False, ittage=False, ras=False, settle=True)
        request = BpuRedirect(pc + 0x100, source.meta.redirect,
            cfi_pc=pc + 4 + (int(guarded) << 49), taken=1, branch_type=2)
        # This is an isolated recovery-input boundary control. The high-guard
        # variant does not claim a complete FTQ program producing this PC.
        observation.checker.plan_redirect(source, request)
        async with agent.observe_guarded_redirect() as frames:
            accepted = await agent.redirect(request)
            await agent.next_transaction(start_pc=pc + 0x100, after_tick=accepted)
        assert len(frames) == 1
        assert frames[0] == dict(valid=1, cfi=request.cfi_pc,
            common=request.cfi_pc % (1 << 49), phr=request.cfi_pc)
        await agent.set_ready(prediction=False, meta=True)
        await history.drain()
        observation.checker.raise_failure()
        assert phr.summary()['accepted'] == 1
