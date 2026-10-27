"""Hold an old lookup while learning a new young instruction; no case timing."""
from contextlib import asynccontextmanager
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.driver.recovery import RecoveryDriver
from bpuverify.bpu.env.late_correction_learning import Program as LateProgram
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.early_late_sources import EarlyLateSources


class Program(LateProgram):
    async def from_predecessor(self,source):
        await self.pause()
        return await RecoveryDriver(self.agent,self.checker).send(source,
            position=self.checks.program.recovery_offset,branch_type=2,target=self.checks.program.b)

    async def seed_early(self,predecessor):
        await self.query_successor(predecessor); await self.from_predecessor(predecessor)
        source=await self.source(self.checks.program.b,lambda t:t.early.source in ('ahead','ahead-direction')
            and t.early.branch.position==2,name='real_old_early_conditional_experience')
        self.checks.early_consumer(source)
        return await self.source(self.checks.program.a,lambda t:t.early.source=='ahead'
            and t.early.branch.position==self.checks.program.predecessor_position,
            name='real_later_direct_predecessor')

    async def hold_old_lookup(self,predecessor):
        await self.pause(); prepared=self.checks.open_preparation()
        await RecoveryDriver(self.agent,self.checker).send(predecessor,
            position=self.checks.program.recovery_offset,branch_type=2,target=self.checks.program.b,until=prepared)
        await self.pause()
        self.checks.check(True,self.checker.model.stages[0] is self.checks.prepared,
            'driver held the exact old lookup before its prediction acceptance')

    async def compete(self):
        released=self.checks.open_release()
        if self.checks.program.flowing:
            await self.agent.set_ready(prediction=True,meta=True)
            await self.observation.wait('real_young_source_accepted',lambda _:released.done())
        else:
            await self.agent.accept_predictions_until(released,name='bpu.competing.young_source_accepted',
                failure=lambda:self.checker.failure or self.checks.failure)
        source=await self.agent.next_transaction(start_pc=self.checks.program.b,after_tick=self.checks.selected_tick-1)
        token=self.checks.save(source)
        self.checks.check(self.checks.selected.sequence,token.sequence,'actual old S3 public receipt keeps the selected original')
        await self.pause()
        await self.observation.wait('winning_restore_and_old_learning_confirmed',
            lambda _:self.checks.restoration is not None and self.checks.confirmed is not None)

    async def consume_restored(self):
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=self.checks.program.a,after_tick=self.checks.repair['tick'])
        self.checks.consume_restored(source); await self.pause(); return source


@asynccontextmanager
async def competing_program(agent,checks):
    phr=BpuPhrChecker(scope='different-age S3/S2 correction arbitration',record_limit=8)
    observation=PipelineObservation(agent,checks,sources=EarlyLateSources()); checks.pipeline=observation.checker
    async with observation,agent.observe_phr(phr):
        await agent.reset(checks.program.a)
        anchor=await agent.next_transaction(start_pc=checks.program.a)
        await agent.configure_predictors(ubtb=False,abtb=True,mbtb=True,tage=True,sc=False,ittage=False,ras=False,settle=True)
        yield Program(agent,observation,anchor,checks.program.a)
        phr.summary()
