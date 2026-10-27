"""Reusable real-source program scope for the independent MicroBTB profile."""
from contextlib import asynccontextmanager

from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.transaction.types import BpuRedirect,BpuTraining


class MicroProgram:
    def __init__(self,agent,observation,anchor,pc):
        self.agent,self.observation,self.anchor,self.pc = agent,observation,anchor,pc
        self.checker = observation.checker
        self.micro = self.checker.model.sources.micro

    @staticmethod
    def effects_compared(checker):
        micro = checker.model.sources.micro
        return (micro.learning is None and checker.micro_checked is not None
            and checker.micro_checked[1]==tuple(entry.confidence for entry in micro.entries))

    async def pause(self):
        await self.agent.set_ready(prediction=False,meta=True)
        await self.observation.wait('micro_read_and_feedback_quiet',lambda checker:checker.last_cycle is not None
            and checker.last_cycle.tokens[1:]==(None,None) and self.effects_compared(checker))

    async def capture(self,pc,verify):
        await self.pause()
        boundary = await self.agent.redirect(BpuRedirect(pc,self.anchor.meta.redirect,cfi_pc=self.pc+4))
        await self.agent.set_ready(prediction=True,meta=True)
        source = await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        verify(source)
        await self.pause()
        return source

    async def train(self,pc,source,target,position):
        await self.agent.train(BpuTraining(pc,position,target,source.meta.resolve,branch_type=2))
        await self.observation.wait('micro_training_effect_visible',lambda checker:self.effects_compared(checker)
            and checker.model.sources.resident(pc))

    async def train_burst(self,transactions):
        ticks = await self.agent.train_batches(tuple(transactions))
        await self.observation.wait('micro_adjacent_effects_visible',lambda checker:self.effects_compared(checker)
            and checker.last_resolution is not None and checker.micro_checked[0]>checker.last_resolution[0])
        return ticks


@asynccontextmanager
async def micro_program(agent,pc):
    phr = BpuPhrChecker(scope='independent MicroBTB with coherent backpressured sources')
    async with PipelineObservation(agent) as observation,agent.observe_phr(phr):
        await agent.reset(pc)
        anchor = await agent.next_transaction(start_pc=pc)
        await agent.configure_predictors(ubtb=True,abtb=False,mbtb=False,tage=False,sc=False,
            ittage=False,ras=False,settle=True)
        yield MicroProgram(agent,observation,anchor,pc)
        phr.summary()
