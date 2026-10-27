"""Original-source indirect feedback and autonomous allocation admission."""
from contextlib import asynccontextmanager

from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.env.branch_targets import BranchTargetProgram
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.indirect_sources import IndirectSources
from bpuverify.bpu.transaction.types import BpuRedirect


class IndirectProgram(BranchTargetProgram):
    async def resolve(self,source,*branches):return await super().resolve(source,*branches,retire=False)

    async def capture(self,pc,verify):
        await self.pause()
        request=BpuRedirect(pc,self.anchor.meta.redirect,cfi_pc=self.pc+4)
        self.checker.plan_redirect(self.anchor,request)
        boundary=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        verify(source);await self.pause();return source

    async def capture_path(self,pc,via=None):
        if via is None:return await self.capture_source(pc)
        origin=await self.capture_source(via)
        request=BpuRedirect(pc,origin.meta.redirect,cfi_pc=via+4)
        self.checker.plan_redirect(origin,request)
        boundary=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        self.checker.source_token(source);await self.pause()
        self.checker.retire_source(origin.meta_tick);return source

    async def cold_source(self,pc,*,table,via=None,timeout_requests=128):
        for _ in range(timeout_requests):
            source=await self.capture_path(pc,via)
            token=self.checker.source_token(source)
            prediction=self.checker.model.sources.snapshot(token,resolved=True)
            if prediction.prediction is not None and prediction.prediction.provider is None and prediction.allocation==table:
                return source
            self.checker.retire_source(source.meta_tick)
        raise TimeoutError(f'owned cold ITTAGE allocation table={table}, tick={self.checker.last_tick}, '
            f'independent_random={self.checker.model.sources.random}')


@asynccontextmanager
async def indirect_program(agent,pc):
    phr=BpuPhrChecker(scope='autonomous MainBTB/ITTAGE and original-source full history')
    async with PipelineObservation(agent,sources=IndirectSources()) as observation,agent.observe_phr(phr):
        await agent.reset(pc)
        anchor=await agent.next_transaction(start_pc=pc)
        await agent.set_ready(prediction=False,meta=True)
        await agent.configure_predictors(ubtb=False,abtb=False,mbtb=True,tage=False,sc=False,ittage=True,ras=False,settle=True)
        yield IndirectProgram(agent,observation,anchor,pc)
        phr.summary()
