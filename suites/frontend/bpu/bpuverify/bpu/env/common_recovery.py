"""Normal branch learning, public recovery driver and predicate-based waits."""
from contextlib import asynccontextmanager
from functools import partial

from bpuverify.bpu.checker.common_recovery import CommonRecoveryChecks
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.env.common_history import CommonProgram
from bpuverify.bpu.env.main_service import branch
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.common_history import LOOKUP_WINDOW_CAPACITY
from bpuverify.bpu.model.common_recovery import PC, FORWARD, BACKWARD, BRIDGE
from bpuverify.bpu.model.main_sources import BranchTargetSources
from bpuverify.bpu.transaction.types import BpuRedirect


class CommonRecoveryProgram(CommonProgram):
    async def prepare(self):
        profile = self.common.profile
        for pc, target in ((FORWARD, FORWARD), (BACKWARD, BACKWARD), (BRIDGE, PC)):
            source = await self.capture_source(pc)
            await self.resolve(source, branch(5, target, 2, wrong=True))
        source = await self.capture_source(PC)
        await self.resolve(source, branch(5, PC, 1, wrong=True))
        source = await self.capture_source(PC)
        await self.resolve(source, branch(1, profile.first_target, 1, wrong=True))
        if not profile.first_taken:
            for wrong in (True, False):
                source = await self.capture_source(PC)
                await self.resolve(source, branch(1, PC, 1, taken=False, wrong=wrong),
                                   branch(5, PC, 1))

    async def start_profile(self):
        request = BpuRedirect(PC, self.anchor.meta.redirect, cfi_pc=PC + 4)
        self.checker.plan_redirect(self.anchor, request)
        self.common.plan(self.anchor, request)
        await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True, meta=True)
        await self.observation.wait('declared_loop_has_independent_history_fixed_point',
            lambda _: self.common.stable >= LOOKUP_WINDOW_CAPACITY
                and self.common.model.value == self.common.profile.original)
        while True:
            source = await self.agent.next_transaction(start_pc=PC)
            token = self.checker.source_token(source)
            if token.history.sequence in self.common.sources:
                self.common.original_source(source)
                return source

    async def recover_profile(self, source):
        await self.agent.set_ready(prediction=False, meta=True)
        correction = self.common.profile.correction
        request = BpuRedirect(correction.target, source.meta.redirect, cfi_pc=PC + correction.position,
                              taken=int(correction.taken), branch_type=int(correction.kind))
        self.checker.plan_redirect(source, request)
        self.common.plan(source, request)
        before = self.common.model.recoveries
        tick = await self.agent.redirect(request)
        await self.observation.wait('declared_original_prefix_restored',
            lambda _: self.common.last_recovery is not None and self.common.last_recovery[0] == tick
                and self.common.model.recoveries > before and self.common.last_tick > tick + 2)
        self.common.recovered(tick)
        return tick

    async def consume_profile(self, *, after_tick):
        await self.agent.set_ready(prediction=True, meta=True)
        await self.observation.wait('recovered_history_visible_to_independent_direct_consumer',
            lambda _: self.common.stable >= LOOKUP_WINDOW_CAPACITY
                and self.common.model.value == self.common.profile.consumer)
        while True:
            source = await self.agent.next_transaction(start_pc=self.common.profile.correction.target,
                                                       after_tick=after_tick)
            token = self.checker.source_token(source)
            if token.history.sequence in self.common.sources:
                self.common.consumed(source)
                return source


@asynccontextmanager
async def common_recovery_program(agent, profile, coverage):
    phr = BpuPhrChecker(scope='autonomous branch sources and actual conditional-prefix recovery')
    factory = partial(CommonRecoveryChecks, profile=profile, coverage=coverage)
    async with PipelineObservation(agent, sources=BranchTargetSources(), with_common_history=True,
            common_history_factory=factory) as observation, agent.observe_phr(phr):
        common = observation.common
        await agent.reset(PC)
        anchor = await agent.next_transaction(start_pc=PC)
        common.register_anchor(anchor)
        await agent.configure_predictors(ubtb=True, abtb=False, mbtb=True, tage=False, sc=False,
                                        ittage=False, ras=False, settle=True)
        yield CommonRecoveryProgram(agent, observation, anchor, common)
        common.raise_failure()
        phr.summary()
