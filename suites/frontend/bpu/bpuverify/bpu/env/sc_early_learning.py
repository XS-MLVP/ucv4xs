"""Reuse legal loop operations; the case never manipulates edges or tasks."""
from contextlib import asynccontextmanager

from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.driver.recovery import RecoveryDriver
from bpuverify.bpu.env.conditional_prefix import Program as PrefixProgram
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.pipeline import Outcome
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.statistical_joint_sources import StatisticalJointSources


class Program(PrefixProgram):
    async def query_pc(self,anchor,pc):
        await self.pause()
        boundary = await RecoveryDriver(self.agent,self.checker).send(anchor,
            position=self.checks.program.recovery_offset,branch_type=int(Kind.DIRECT),target=pc)
        source = await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        self.checks.save(source)
        await self.pause()
        return source

    async def teaching_outcome(self,name,source,*,taken,maximum=False):
        token = self.checker.source_token(source)
        late = self.checks.bank.statistical_snapshot(token,resolved=True).late.branch
        wrong = late.position!=2 if taken else late.position==2
        outcomes = (Outcome(2,self.checks.program.d,Kind.CONDITIONAL,taken,mispredict=wrong),)
        if not taken:
            outcomes += (Outcome(4,self.checks.program.a,Kind.DIRECT,True),)
        await self.feedback(name,source,*outcomes,maximum=maximum)

    async def observe_teacher(self,anchor):
        c,p = self.checks,self.checks.program
        accepted = c.open()
        await RecoveryDriver(self.agent,self.checker).send(anchor,position=p.recovery_offset,
            branch_type=int(Kind.DIRECT),target=p.b,until=None if p.flowing else accepted)
        await self.observation.wait('real_SC_early_conditional_S1',lambda _:accepted.done(),timeout_cycles=256)
        await self.observation.wait('same_original_SC_final_repair',lambda _:c.SC_witness is not None)
        source = await self.agent.next_transaction(start_pc=p.b,after_tick=c.selected_tick-1)
        c.save(source)
        await self.pause()
        await self.observation.wait('actual_original_SC_short_learning',lambda _:c.confirmed is not None)
        await self.agent.set_ready(prediction=True,meta=True)
        await self.observation.wait('natural_SC_taught_early_consumer',
            lambda _:c.new_a is not None and c.new_b is not None,timeout_cycles=256)
        # Collect passively frozen original owners together, with no pause
        # between A and B that would create another prediction experiment.
        for pc,record in ((p.a,c.new_a),(p.b,c.new_b)):
            token = self.checker.source_receipts[record['tick']]
            receipt = await self.agent.next_transaction(start_pc=pc,after_tick=self.checker.s1_accepts[token.sequence]-1)
            c.check(token.sequence,c.save(receipt).sequence,'complete natural consumer receipt matches the compared owner')
        await self.pause()
        await self.observation.wait('new_consumer_own_protection_loss_confirmed',lambda _:c.consumer_confirmed is not None)


@asynccontextmanager
async def experiment(agent,checks):
    phr = BpuPhrChecker(scope='SC final prediction teaches its real original early conditional',record_limit=8)
    observation = PipelineObservation(agent,checks,sources=StatisticalJointSources())
    checks.pipeline = observation.checker
    async with observation,agent.observe_phr(phr):
        await agent.reset(checks.program.a)
        anchor = await agent.next_transaction(start_pc=checks.program.a)
        env = Program(agent,observation,anchor,checks.program.a)
        await env.pause()
        await agent.configure_predictors(ubtb=False,abtb=True,mbtb=True,tage=True,
            sc=False,ittage=True,ras=False,settle=True)
        yield env
        phr.summary()
