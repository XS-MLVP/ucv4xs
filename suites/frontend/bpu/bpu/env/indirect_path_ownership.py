"""Owned high-level source/feedback operations; case owns instruction sequence."""
from contextlib import asynccontextmanager
from suites.frontend.bpu.bpu.env.late_correction_learning import Program as ExistingProgram
from suites.frontend.bpu.bpu.driver.recovery import RecoveryDriver
from suites.frontend.bpu.bpu.model.indirect_path_ownership import resolution
from suites.frontend.bpu.bpu.model.pipeline import Outcome, Resolution
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback
from suites.frontend.bpu.tage.model.semantic import TABLES
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.model.early_joint_sources import EarlyJointSources


class Program(ExistingProgram):
    async def controls(self, *, early=None, target=None):
        await self.pause()
        values = {}
        if early is not None:
            values['abtb'] = early
        if target is not None:
            values['ittage'] = target
        await self.agent.configure_predictors(**values, settle=True)
        await self.pause()

    async def resolve_owned(self, phase, source):
        await self.pause()
        self.checks.plan_resolution(phase, source)
        pc, position, target, kind, taken, wrong = resolution(self.checks.program, phase)
        transaction = BpuBatchTraining(pc, source.meta.resolve,
            (BpuBranchFeedback(position, target, kind, taken=int(taken), mispredict=int(wrong)),))
        self.checker.plan_feedback(source, transaction)
        if phase == 'not-taken':
            token = self.checker.source_token(source)
            semantic = Resolution(token.history, pc,
                (Outcome(position, target, Kind(kind), taken, mispredict=wrong),), origin=token)
            feedback = self.checker.model.sources.feedback_for(semantic)
            attempts = 0
            def has_room(_):
                nonlocal attempts
                self.checker.raise_failure()
                attempts += 1
                candidate = self.checker.model.sources.tage.allocation_at_next_accept(feedback)
                if candidate is None:
                    raise AssertionError('declared negative outcome has no allocation opportunity')
                if candidate[0] < TABLES - 1:
                    return True
                if attempts >= 128:
                    raise TimeoutError('semantic allocation-room admission budget')
                return False
            with self.agent.training_driver.admit_when(has_room):
                await self.agent.train_batch(transaction)
        else:
            await self.agent.train_batch(transaction)
        await self.pause()



@asynccontextmanager
async def experiment(agent, checks):
    phr = BpuPhrChecker(scope='original direction/indirect-target lifetime with atomic closure', record_limit=8)
    observation = PipelineObservation(agent, checks, sources=EarlyJointSources())
    checks.pipeline = observation.checker
    async with observation, agent.observe_phr(phr):
        await agent.reset(checks.program.a)
        anchor = await agent.next_transaction(start_pc=checks.program.a)
        await agent.configure_predictors(ubtb=False, abtb=True, mbtb=True, tage=True,
            sc=False, ittage=True, ras=False, settle=True)
        yield Program(agent, observation, anchor, checks.program.a)
        phr.summary()
