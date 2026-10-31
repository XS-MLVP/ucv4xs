"""Real branch outcomes, controlled admission and passive original-S3 checks."""
from contextlib import asynccontextmanager

from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.driver.recovery import RecoveryDriver
from suites.frontend.bpu.bpu.env.cross_block_learning import Program as CrossBlockProgram
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.model.early_late_sources import EarlyLateSources
from suites.frontend.bpu.bpu.model.late_correction_learning import weak_late_alternate
from suites.frontend.bpu.bpu.model.early_opposition import provider
from suites.frontend.bpu.bpu.model.pipeline import Resolution,Outcome
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback
from suites.frontend.bpu.tage.model.semantic import TABLES,HISTORIES


class Program(CrossBlockProgram):
    async def source(self,pc,predicate=lambda _:True,*,name='owned_program_source'):
        await self.agent.set_ready(prediction=True,meta=True)
        previous=self.pc; self.pc=pc
        try: return await self.consume(name,predicate)
        finally: self.pc=previous

    async def early_enabled(self,value):
        await self.pause()
        await self.agent.configure_predictors(abtb=value,settle=True)
        await self.pause()

    async def resolve_owned(self,phase,source):
        await self.pause(); self.checks.plan_resolution(phase,source)
        pc,position,target,kind,taken,wrong=self.checks.program.resolution(phase)
        branch=BpuBranchFeedback(position,target,kind,taken=int(taken),mispredict=int(wrong))
        transaction=BpuBatchTraining(pc,source.meta.resolve,(branch,))
        self.checker.plan_feedback(source,transaction)
        if phase!='not-taken':
            await self.agent.train_batch(transaction)
        else:
            token=self.checker.source_token(source)
            request=Resolution(token.history,pc,(Outcome(position,target,Kind(kind),taken,mispredict=wrong),),origin=token)
            feedback=self.checker.model.sources.feedback_for(request)
            attempts=0
            def room(_):
                nonlocal attempts
                self.checker.raise_failure(); attempts+=1
                candidate=self.checker.model.sources.tage.allocation_at_next_accept(feedback)
                if candidate is None: raise ValueError('real NT outcome has no longer-history allocation opportunity')
                if candidate[0]<TABLES-1: return True
                if attempts>=128: raise TimeoutError('no room for a later history specialization within admission budget')
                return False
            # A semantic capacity requirement, not an enumerated bank/way.
            with self.agent.training_driver.admit_when(room): await self.agent.train_batch(transaction)
        await self.pause()

    async def seed_early(self,predecessor):
        await self.query_successor(predecessor)
        await self.from_predecessor(predecessor)
        source=await self.source(self.checks.program.b,lambda t:t.early.source in ('ahead','ahead-direction')
            and t.early.branch.position==2,name='real_early_conditional_experience')
        self.checks.early_consumer(source)
        return await self.source(self.checks.program.a,lambda t:t.early.source=='ahead'
            and t.early.branch.position==4,name='fresh_predecessor_after_early_learning')

    async def stable_predecessor(self,predecessor):
        await self.from_predecessor(predecessor)
        source=await self.source(self.checks.program.a,
            lambda t:t.history.history%(1<<max(HISTORIES))==self.checks.program.stable_predecessor_history,
            name='actual_stable_later_path_history')
        self.checks.stable_predecessor(source); return source

    async def weak_control(self,predecessor):
        await self.from_predecessor(predecessor)
        source=await self.source(self.checks.program.b,
            lambda t:weak_late_alternate(self.checker.model.sources,t),name='independent_weak_late_alternate_control')
        self.checks.weak_consumer(source); return source

    async def original_teacher(self,predecessor):
        await self.pause(); accepted=self.checks.open_original()
        await RecoveryDriver(self.agent,self.checker).send(predecessor,
            position=self.checks.program.recovery_offset,branch_type=2,target=self.checks.program.b,
            until=None if self.checks.program.flowing else accepted)
        await self.observation.wait('qualified_original_S1_admitted',lambda _:accepted.done(),timeout_cycles=256)
        source=await self.agent.next_transaction(start_pc=self.checks.program.b,after_tick=self.checks.selected_tick-1)
        self.checks.window_receipt(source)
        await self.pause()
        await self.observation.wait('original_S3_learning_actually_confirmed',lambda _:self.checks.confirmed is not None)
        return source

    async def consume_learned(self):
        # Follow the actual S3-restored path. Another redirect is a different
        # experiment: it replaces the preserved Ahead read ancestor.
        def learned(token):
            value=provider(self.checker.model.sources,token); record=self.checks.confirmed
            return (value is not None and record is not None and value.table==0 and value.counter<4
                and (value.index,value.tag)==(record['index'],record['tag']))
        source=await self.source(self.checks.program.b,learned,name='new_original_consumes_S3_taught_direction')
        self.checks.negative_consumer(source); return source


@asynccontextmanager
async def late_correction_program(agent,checks):
    p=checks.program
    phr=BpuPhrChecker(scope='one original early/middle/final teaching lifetime',record_limit=8)
    observation=PipelineObservation(agent,checks,sources=EarlyLateSources()); checks.pipeline=observation.checker
    async with observation,agent.observe_phr(phr):
        await agent.reset(p.a)
        anchor=await agent.next_transaction(start_pc=p.a)
        await agent.configure_predictors(ubtb=False,abtb=True,mbtb=True,tage=True,sc=False,
            ittage=False,ras=False,settle=True)
        yield Program(agent,observation,anchor,p.a)
        phr.summary()
