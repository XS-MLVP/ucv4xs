"""Driver ownership and bounded observation stay outside the scenario."""
from contextlib import asynccontextmanager
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.env.branch_targets import BranchTargetProgram
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.ahead_sources import AheadSources
from bpuverify.bpu.transaction.types import BpuRedirect


class AheadProgram(BranchTargetProgram):
    async def run_loop(self,pc,checks,*,source_pc):
        await self.pause()
        await self.agent.redirect(BpuRedirect(pc,self.anchor.meta.redirect,cfi_pc=self.pc+4))
        await self.agent.set_ready(prediction=True,meta=True)
        await self.observation.wait('both_independent_ahead_targets_consumed',lambda _:len(checks.consumed)==2,timeout_cycles=256)
        source=await self.agent.next_transaction(start_pc=source_pc,require_taken=True)
        self.checker.source_token(source)
        await self.pause()
        return source

    async def consume_target(self,pc):
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc)
        self.checker.source_token(source)
        await self.pause()
        return source

    async def disabled_fallback(self,source,pc):
        await self.pause()
        self.checker.source_token(source)
        await self.agent.configure_predictors(abtb=False,settle=True)
        # Use the fresh post-recovery owner, not an arbitrarily old anchor
        # whose physical PHR high bits may no longer be retained.
        boundary=await self.agent.redirect(BpuRedirect(pc,source.meta.redirect,
            cfi_pc=source.prediction.start_pc+4,taken=1,branch_type=3))
        await self.agent.set_ready(prediction=True,meta=True)
        consumer=await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        self.checker.source_token(consumer)
        await self.pause()
        return consumer


@asynccontextmanager
async def ahead_program(agent,pc,checks):
    phr=BpuPhrChecker(scope='independent ahead read/fastTrain/MainBTB ownership')
    observation=PipelineObservation(agent,checks,sources=AheadSources())
    checks.pipeline=observation.checker
    async with observation,agent.observe_phr(phr):
        await agent.reset(pc)
        anchor=await agent.next_transaction(start_pc=pc)
        await agent.configure_predictors(ubtb=False,abtb=True,mbtb=True,tage=False,sc=False,ittage=False,ras=False,settle=True)
        yield AheadProgram(agent,observation,anchor,pc)
        phr.summary()
