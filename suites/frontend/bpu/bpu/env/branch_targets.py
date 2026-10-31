"""Real sources and driver feedback around independently composed BTBs."""
from contextlib import asynccontextmanager

from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.env.micro import MicroProgram
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.model.main_sources import BranchTargetSources
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining


class BranchTargetProgram(MicroProgram):
    async def pause(self):
        await self.agent.set_ready(prediction=False,meta=True)
        await self.agent.wait_training(committed=True)
        await self.observation.wait('branch_target_sources_quiet',lambda checker:checker.last_cycle is not None
            and checker.last_cycle.tokens[1:]==(None,None) and self.effects_compared(checker)
            and not checker.model.sources.main_pending())

    async def capture_source(self,pc):
        return await self.capture(pc,self.checker.source_token)

    async def resolve(self,source,*branches,retire=True):
        transaction = BpuBatchTraining(source.prediction.start_pc,source.meta.resolve,tuple(branches))
        self.checker.plan_feedback(source,transaction)
        await self.agent.train_batch(transaction)
        await self.pause()
        result = self.checker.last_resolution
        if retire:self.checker.retire_source(source.meta_tick)
        return result


@asynccontextmanager
async def branch_target_program(agent,pc):
    phr = BpuPhrChecker(scope='independent MicroBTB/MainBTB and exact learning owners')
    async with PipelineObservation(agent,sources=BranchTargetSources()) as observation,agent.observe_phr(phr):
        await agent.reset(pc)
        anchor = await agent.next_transaction(start_pc=pc)
        await agent.configure_predictors(ubtb=True,abtb=False,mbtb=True,tage=False,sc=False,
            ittage=False,ras=False,settle=True)
        yield BranchTargetProgram(agent,observation,anchor,pc)
        phr.summary()
