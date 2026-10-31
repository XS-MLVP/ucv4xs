"""Ordinary BPU drivers plus autonomous prediction and retirement checks."""
from contextlib import asynccontextmanager

from suites.frontend.bpu.bpu.env.main_service import MainProgram
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.env.ras.retirement import BpuRetirement
from suites.frontend.bpu.bpu.model.return_stack_sources import ReturnStackSources
from suites.frontend.bpu.bpu.model.owned_return_stack import CALL,RETURN,POSITION,STATIC_TARGET
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect,BpuBranchFeedback


class OwnedReturnEnvironment(MainProgram):
    def __init__(self,agent,observation,anchor,retirement):
        super().__init__(agent,observation,anchor,CALL)
        self.retirement=retirement

    async def capture(self,pc,verify):
        await self.pause()
        request=BpuRedirect(pc,self.anchor.meta.redirect,cfi_pc=CALL+4,branch_type=3)
        self.checker.plan_redirect(self.anchor,request)
        tick=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=tick)
        verify(source)
        await self.pause()
        return source

    async def learn(self):
        originals=[]
        for pc,target,kind,action in ((CALL,RETURN,2,2),(RETURN,STATIC_TARGET,3,1)):
            source=await self.capture_source(pc)
            originals.append(source)
            await self.resolve(source,BpuBranchFeedback(POSITION,target,kind,ras_action=action,mispredict=1))
        return originals

    async def recover(self,source,target,*,action):
        request=BpuRedirect(target,source.meta.redirect,cfi_pc=source.meta.perf.start_pc+POSITION,
            branch_type=2 if action==2 else 3,ras_action=action)
        self.checker.plan_redirect(source,request)
        tick=await self.agent.redirect(request)
        await self.pause()
        return tick

    async def retire(self,operations):
        for source,action in operations:
            self.checker.plan_commit(source,action)
        await self.retirement.retire_many(operations)
        await self.pause()

    async def next_source(self,pc,*,after_tick):
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=after_tick)
        self.checker.source_token(source)
        await self.pause()
        return source


@asynccontextmanager
async def owned_return_environment(agent,program):
    async with PipelineObservation(agent,sources=ReturnStackSources()) as observation:
        async with BpuRetirement(agent,semantic=observation.checker) as retirement:
            await agent.reset(CALL)
            anchor=await agent.next_transaction(start_pc=CALL)
            observation.checker.source_token(anchor)
            environment=OwnedReturnEnvironment(agent,observation,anchor,retirement)
            # The SC composition profile requires a drained pipeline before
            # changing its enable; no fixed settling cycles or ignored reads.
            await environment.pause()
            await agent.configure_predictors(ubtb=program.micro,abtb=False,mbtb=True,tage=False,
                sc=False,ittage=False,ras=False,settle=True)
            yield environment
