"""Source capture and normal SDK feedback; no pin timing in the case."""
from contextlib import asynccontextmanager

from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect
from suites.frontend.bpu.bpu.env.tage_semantic import TageSemanticEnvironment
from suites.frontend.bpu.bpu.model.tage.interleaved import PC,TRACKED,OWNERS,target,opposing_base_program
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback,BpuTraining


class InterleavedProgram:
    def __init__(self,agent,env,anchor):
        self.agent,self.env,self.anchor,self.checker = agent,env,anchor,env.reference

    async def query(self,positions=(),*,tage=True):
        source = await revisit_from_redirect(self.agent,PC,self.anchor)
        self.checker.raise_failure()
        if tage:
            for position in positions:self.checker.source_expected(source,position)
        return source

    async def resolve(self,source,outcomes):
        await self.agent.train_batch_with_prediction_pause(BpuBatchTraining(PC,source.meta.resolve,
            tuple(BpuBranchFeedback(position,target(position),1,taken=int(taken),mispredict=int(wrong))
                for position,taken,wrong in outcomes)))
        self.checker.raise_failure()

    async def establish_owners(self):
        source = await self.query()
        known = []
        for position,owner in zip(TRACKED,OWNERS,strict=True):
            await self.agent.train(BpuTraining(PC,position,target(position),source.meta.resolve,branch_type=1))
            known.append(position)
            source = await self.query(known)
            self.checker.prepared(source,position,'main-only')
            request = BpuBatchTraining(PC,source.meta.resolve,(
                BpuBranchFeedback(position,target(position),1,taken=0,mispredict=1),))
            await self.env.allocate(source,request,owner=owner)
            source = await self.query(known)
            self.checker.prepared(source,position,'allocated')
            await self.resolve(source,((position,False,False),))
            source = await self.query(known)
            self.checker.prepared(source,position,'strong')

    async def oppose_bases(self):
        await self.agent.configure_predictors(tage=False,settle=True)
        for outcomes in opposing_base_program():
            source = await self.query(tage=False)
            await self.resolve(source,outcomes)
        await self.agent.configure_predictors(tage=True,settle=True)
        return await self.query(TRACKED)


@asynccontextmanager
async def interleaved_program(agent,checker):
    async with TageSemanticEnvironment(agent,checker) as env:
        await agent.reset(PC)
        anchor = (await agent.next_transaction(start_pc=PC)).meta.redirect
        await agent.configure_predictors(ubtb=False,abtb=False,mbtb=True,tage=True,
            sc=False,ittage=False,ras=False,settle=True)
        yield InterleavedProgram(agent,env,anchor)
