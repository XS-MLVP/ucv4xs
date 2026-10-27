"""High-level owned feedback and control operations; semantic flow lives in case."""
from contextlib import asynccontextmanager

from toffee import ClockCycles
from bpuverify.bpu.env.late_correction_learning import Program as ExistingProgram
from bpuverify.bpu.driver.recovery import RecoveryDriver
from bpuverify.bpu.model.pipeline import Outcome, Resolution
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback
from bpuverify.tage.model.semantic import TABLES
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.early_joint_sources import EarlyJointSources
from bpuverify.bpu.monitor.unexecuted_indirect import actual_target_guard


class Program(ExistingProgram):
    async def controls(self, **values):
        await self.pause()
        await self.agent.configure_predictors(**values, settle=True)
        await self.pause()

    async def from_predecessor(self, source):
        await self.pause()
        return await RecoveryDriver(self.agent, self.checker).send(source,
            position=self.checks.program.recovery_offset, branch_type=int(Kind.DIRECT), target=self.checks.program.b)

    async def feedback(self, name, source, *outcomes, maximum=False):
        await self.pause()
        self.checks.plan(name, source, outcomes)
        token = self.checker.source_token(source)
        transaction = BpuBatchTraining(token.pc, source.meta.resolve, tuple(BpuBranchFeedback(
            branch.position, branch.target, int(branch.kind), taken=int(branch.taken), mispredict=int(branch.mispredict))
            for branch in outcomes))
        self.checker.plan_feedback(source, transaction)
        if maximum:
            request = Resolution(token.history, token.pc, tuple(outcomes), origin=token)
            feedback = self.checker.model.sources.feedback_for(request)
            attempts = 0
            def admitted(_):
                nonlocal attempts
                self.checker.raise_failure()
                attempts += 1
                value = self.checker.model.sources.tage.allocation_at_next_accept(feedback)
                if value is not None and value[0] == TABLES - 1: return True
                if attempts >= 128: raise TimeoutError('maximum semantic history capacity admission budget')
                return False
            with self.agent.training_driver.admit_when(admitted): await self.agent.train_batch(transaction)
        else: await self.agent.train_batch(transaction)
        await self.pause()

    async def conditional(self, name, source, *, taken=True, wrong=True, indirect=False,
            indirect_target=None, indirect_wrong=False, maximum=False):
        p = self.checks.program
        outcomes = (Outcome(2, p.d, Kind.CONDITIONAL, taken, mispredict=wrong),)
        if indirect:
            if taken: raise ValueError('unexecuted younger indirect cannot appear in a taken conditional prefix')
            outcomes += (Outcome(4, p.a if indirect_target is None else indirect_target, Kind.INDIRECT,
                True, mispredict=indirect_wrong),)
        await self.feedback(name, source, *outcomes, maximum=maximum)

    async def query_owned(self, anchor):
        source = await self.query_successor(anchor)
        self.checks.save(source)
        return source

    async def drain_bank_writes(self, cycles=16):
        """Hold prediction long enough for single-port bank writes to retire."""
        await self.pause()
        await self.agent.set_ready(prediction=False, meta=True)
        await ClockCycles(self.agent.dut.clock, cycles)
        await self.agent.set_ready(prediction=True, meta=True)



@asynccontextmanager
async def experiment(agent, checks):
    observation = PipelineObservation(agent, checks, sources=EarlyJointSources())
    checks.pipeline = observation.checker
    phr = BpuPhrChecker(scope='atomic original conditional ownership excludes unexecuted indirect learning', record_limit=8)
    async with observation, agent.observe_phr(phr), actual_target_guard(agent, checks):
        await agent.reset(checks.program.a)
        anchor = await agent.next_transaction(start_pc=checks.program.a)
        await agent.configure_predictors(ubtb=False, abtb=True, mbtb=True, tage=True,
            sc=False, ittage=True, ras=False, settle=True)
        yield Program(agent, observation, anchor, checks.program.a)
        phr.summary()
