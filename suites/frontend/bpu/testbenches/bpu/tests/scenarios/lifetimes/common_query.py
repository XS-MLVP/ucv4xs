"""Reuse existing legal loop/recovery programs with stronger original histories."""
from contextlib import asynccontextmanager
from functools import partial
from suites.frontend.bpu.testbenches.bpu.env.bundle.common_query import common_query_binding
from suites.frontend.bpu.testbenches.bpu.checker.common_query import CommonQueryChecks
from suites.frontend.bpu.testbenches.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.loop_iteration import LoopIterationProgram
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.loop_iteration import FinalIterationProgram
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.common_recovery import CommonRecoveryProgram
from suites.frontend.bpu.testbenches.bpu.model.common_recovery import PROFILES as RECOVERY_PROFILES
from suites.frontend.bpu.testbenches.bpu.env.agent.pipeline import PipelineObservation
from suites.frontend.bpu.testbenches.bpu.model.loop_iteration import PC
from suites.frontend.bpu.testbenches.bpu.model.main_sources import BranchTargetSources
from suites.frontend.bpu.testbenches.bpu.model.direction_sources import DirectionSources


class TwoConditionQueryProgram(LoopIterationProgram):
    async def prepare(self):
        self.common.profile = next(profile for profile in RECOVERY_PROFILES if profile.name == 'direct-after-prefix')
        await CommonRecoveryProgram.prepare(self)


@asynccontextmanager
async def common_query_program(agent, *, final=False, mixed=False, coverage=None):
    phr = BpuPhrChecker(scope='autonomous sources, exact public receipt association and owned S0 histories')
    async with PipelineObservation(agent, sources=DirectionSources() if final else BranchTargetSources(),
            with_common_history=True, common_history_factory=partial(CommonQueryChecks, query_coverage=coverage),
            common_history_binding_factory=common_query_binding) as observation, agent.observe_phr(phr):
        await agent.reset(PC)
        anchor = await agent.next_transaction(start_pc=PC)
        common = observation.common
        common.register_anchor(anchor)
        await agent.set_ready(prediction=False, meta=True)
        await agent.configure_predictors(ubtb=not final, abtb=False, mbtb=True, tage=False,
            sc=False, ittage=False, ras=False, settle=True)
        yield (FinalIterationProgram(agent, observation, anchor, common) if final else
               (TwoConditionQueryProgram if mixed else LoopIterationProgram)(agent, observation, anchor, common))
        common.raise_failure()
        phr.summary()
