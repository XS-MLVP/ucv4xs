"""Normal driver ownership and two-source observation; no test clock loops."""
from contextlib import asynccontextmanager

from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.env.directions import DirectionProgram
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.model.joint_sources import JointLateSources


class JointProgram(DirectionProgram):
    async def capture(self,pc,verify):
        await self.pause()
        request=BpuRedirect(pc,self.anchor.meta.redirect,cfi_pc=self.pc+4)
        self.checker.plan_redirect(self.anchor,request)
        boundary=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        verify(source)
        await self.pause()
        return source

    async def configure_late(self,enabled):
        await self.pause()
        await self.agent.configure_predictors(tage=enabled,ittage=enabled,settle=True)

    async def capture_via(self,pc,via):
        intermediate=await self.capture_source(via)
        request=BpuRedirect(pc,intermediate.meta.redirect,cfi_pc=via+4)
        self.checker.plan_redirect(intermediate,request)
        boundary=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        self.checker.source_token(source)
        await self.pause()
        self.checker.retire_source(intermediate.meta_tick)
        return source


@asynccontextmanager
async def joint_program(agent,pc):
    phr=BpuPhrChecker(scope='joint original-window Main/TAGE/ITTAGE, no observed-component oracle')
    async with PipelineObservation(agent,sources=JointLateSources()) as observation,agent.observe_phr(phr):
        await agent.reset(pc)
        anchor=await agent.next_transaction(start_pc=pc)
        await agent.set_ready(prediction=False,meta=True)
        await agent.configure_predictors(ubtb=False,abtb=False,mbtb=True,tage=True,sc=False,
            ittage=True,ras=False,settle=True)
        yield JointProgram(agent,observation,anchor,pc)
        phr.summary()
