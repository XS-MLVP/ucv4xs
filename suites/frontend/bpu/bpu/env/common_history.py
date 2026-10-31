"""Semantic history monitoring and real backend recovery stay below cases."""
from contextlib import asynccontextmanager
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.env.main_service import MainProgram,branch
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.model.main_sources import BranchTargetSources
from suites.frontend.bpu.bpu.model.common_history import Value,LOOKUP_WINDOW_CAPACITY
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect

PC=0x40000800
LATER_POSITION,POSITION=5,1
FALL=PC+0x200


class CommonProgram(MainProgram):
    def __init__(self,agent,observation,anchor,common):
        super().__init__(agent,observation,anchor,PC);self.common=common

    async def capture(self,pc,verify):
        await self.pause();request=BpuRedirect(pc,self.anchor.meta.redirect,cfi_pc=PC+4)
        self.checker.plan_redirect(self.anchor,request);self.common.plan(self.anchor,request)
        tick=await self.agent.redirect(request);await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=tick)
        verify(source);self.common.raise_failure();await self.pause();return source

    async def start_loop(self,*,later_conditional):
        request=BpuRedirect(PC,self.anchor.meta.redirect,cfi_pc=PC+4)
        self.checker.plan_redirect(self.anchor,request);self.common.plan(self.anchor,request)
        await self.agent.redirect(request);await self.agent.set_ready(prediction=True,meta=True)
        def fixed(_):self.common.raise_failure();return self.common.stable>=LOOKUP_WINDOW_CAPACITY and self.common.model.value==Value(True,65535,255)
        await self.observation.wait('independent_conditional_history_fixed_point',fixed)
        while True:
            source=await self.agent.next_transaction(start_pc=PC)
            token=self.checker.source_token(source)
            if token.history.sequence in self.common.sources:
                self.common.original_source(source,later_conditional=later_conditional);return source

    async def recover_not_taken(self,source):
        await self.agent.set_ready(prediction=False,meta=True)
        request=BpuRedirect(PC+3,source.meta.redirect,cfi_pc=PC+POSITION,taken=0,branch_type=1)
        self.checker.plan_redirect(source,request);self.common.plan(source,request)
        before=self.common.model.recoveries;tick=await self.agent.redirect(request)
        def restored(_):
            self.common.raise_failure();return self.common.last_recovery is not None and self.common.last_recovery[0]==tick and self.common.model.recoveries>before and self.common.last_tick>tick+2
        await self.observation.wait('original_conditional_prefix_recovered',restored)
        self.common.recovered(tick)
        return tick

    async def consume_recovered_history(self,*,later_conditional,after_tick):
        await self.agent.set_ready(prediction=True,meta=True)
        expected=Value(True,65533,252) if later_conditional else Value(True,65534,254)
        def fixed(_):
            self.common.raise_failure();return self.common.stable>=LOOKUP_WINDOW_CAPACITY and self.common.model.value==expected
        await self.observation.wait('independent_recovered_history_visible_to_fresh_lookup',fixed)
        while True:
            source=await self.agent.next_transaction(start_pc=FALL,after_tick=after_tick)
            token=self.checker.source_token(source)
            if token.history.sequence in self.common.sources:
                self.common.consumed(source,later_conditional=later_conditional);return source


@asynccontextmanager
async def common_program(agent,*,public_only=False,coverage=None):
    phr=BpuPhrChecker(scope='autonomous Main/Micro and conditional-only common history')
    async with PipelineObservation(agent,sources=BranchTargetSources(),with_common_history=True,
            common_history_state=not public_only) as observation,agent.observe_phr(phr):
        common=observation.common
        common.coverage=coverage
        await agent.reset(PC);anchor=await agent.next_transaction(start_pc=PC);common.register_anchor(anchor)
        await agent.configure_predictors(ubtb=True,abtb=False,mbtb=True,tage=False,sc=False,ittage=False,ras=False,settle=True)
        yield CommonProgram(agent,observation,anchor,common);common.raise_failure();phr.summary()


async def prepare(environment,*,later_conditional):
    source=await environment.capture_source(FALL);await environment.resolve(source,branch(5,FALL,2,wrong=True))
    source=await environment.capture_source(PC)
    await environment.resolve(source,branch(LATER_POSITION,FALL,1 if later_conditional else 2,wrong=True))
    source=await environment.capture_source(PC)
    await environment.resolve(source,branch(POSITION,PC,1,wrong=True))
