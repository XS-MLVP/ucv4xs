"""Owned public sources and condition-terminated iteration recovery programs."""
from contextlib import asynccontextmanager
from copy import deepcopy

from suites.frontend.bpu.bpu.bundle.loop_iteration import loop_iteration_binding
from suites.frontend.bpu.bpu.checker.loop_iteration import LoopIterationChecks
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.env.common_history import CommonProgram
from suites.frontend.bpu.bpu.env.directions import DirectionProgram
from suites.frontend.bpu.bpu.env.main_service import branch
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.model.common_history import LOOKUP_WINDOW_CAPACITY
from suites.frontend.bpu.bpu.model.loop_iteration import PC, FORWARD, BACKWARD, POSITION, MAX_ITERATIONS
from suites.frontend.bpu.bpu.model.main_sources import BranchTargetSources
from suites.frontend.bpu.bpu.model.direction_sources import DirectionSources
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect


class LoopIterationProgram(CommonProgram):
    async def prepare(self):
        for pc in (FORWARD, BACKWARD):
            source = await self.capture_source(pc)
            await self.resolve(source, branch(5, pc, 2, wrong=True))
        source = await self.capture_source(PC)
        await self.resolve(source, branch(POSITION, PC, 1, wrong=True))
        # A normally learned Main prediction must repair a cold early choice.
        # Then restore Micro for the uninterrupted natural loop. This creates
        # a genuine repair event rather than assuming training causes one.
        await self.agent.configure_predictors(ubtb=False, settle=True)
        await self.capture_source(PC)
        await self.agent.configure_predictors(ubtb=True, settle=True)

    async def start_loop(self, program):
        request = BpuRedirect(PC, self.anchor.meta.redirect, cfi_pc=PC+4)
        self.checker.plan_redirect(self.anchor, request); self.common.plan(self.anchor, request)
        tick = await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True, meta=True)
        minimum = MAX_ITERATIONS if program.saturated_original else 2 * LOOKUP_WINDOW_CAPACITY
        while True:
            receipt = await self.agent.next_transaction(start_pc=PC, after_tick=tick)
            source = self.common.source(receipt)
            if source.count >= minimum:
                self.common.original_source(receipt, program)
                return receipt

    async def saturate_younger(self):
        await self.observation.wait('younger_loop_reaches_saturation',
            lambda _: self.common.model.cursor == MAX_ITERATIONS,
            timeout_cycles=MAX_ITERATIONS + 4 * LOOKUP_WINDOW_CAPACITY)
        original = self.common.original[1]
        while True:
            receipt = await self.agent.next_transaction(start_pc=PC)
            source = self.common.source(receipt)
            if source.count == MAX_ITERATIONS and source.token_sequence > original.token_sequence:
                self.common.proof['younger_source'] = dict(token=source.token_sequence,
                    count=source.count, meta_tick=receipt.meta_tick)
                break
        await self.pause()
        await self.observation.wait('saturated_loop_held_without_an_outcome',
            lambda _: self.common.last_step.reason == 'hold')
        self.common.saturated_and_held()

    async def recover(self, source, program):
        correction = program.correction
        request = BpuRedirect(correction.target, source.meta.redirect, cfi_pc=PC+correction.position,
            taken=int(correction.taken), branch_type=int(correction.kind))
        self.checker.plan_redirect(source, request); self.common.plan(source, request)
        tick = await self.agent.redirect(request)
        await self.observation.wait('original_iteration_recovery_registered',
            lambda _: self.common.last_recovery is not None and self.common.last_recovery['tick'] == tick
                and self.common.last_recovery.get('registered', False))
        self.common.recovered(tick)
        return tick

    async def consume(self, tick):
        await self.agent.set_ready(prediction=True, meta=True)
        receipt = await self.agent.next_transaction(after_tick=tick)
        self.common.consumed(receipt)
        await self.pause()
        return receipt


@asynccontextmanager
async def loop_iteration_program(agent, coverage):
    phr = BpuPhrChecker(scope='autonomous Micro/Main/PHR and separately owned speculative IMLI versions')
    async with PipelineObservation(agent, sources=BranchTargetSources(), with_common_history=True,
            common_history_factory=LoopIterationChecks,
            common_history_binding_factory=loop_iteration_binding) as observation, agent.observe_phr(phr):
        common = observation.common
        common.coverage = coverage
        await agent.reset(PC)
        anchor = await agent.next_transaction(start_pc=PC)
        common.register_anchor(anchor)
        await agent.configure_predictors(ubtb=True, abtb=False, mbtb=True, tage=False,
            sc=False, ittage=False, ras=False, settle=True)
        yield LoopIterationProgram(agent, observation, anchor, common)
        common.raise_failure(); phr.summary()


class FinalIterationProgram(DirectionProgram):
    def __init__(self, agent, observation, anchor, common):
        super().__init__(agent, observation, anchor, PC)
        self.common = common

    async def capture(self, pc, verify):
        return await CommonProgram.capture(self, pc, verify)

    async def prepare_final_repair(self):
        source = await self.capture_source(PC)
        await self.resolve(source, branch(POSITION, PC, 1, wrong=True))
        await self.enable_tage(True)
        source = await self.capture_source(PC)
        await self.allocate(source, branch(POSITION, PC, 1, taken=False, wrong=True), owner=(3, 0))
        await self.enable_tage(False)
        source = await self.capture_source(PC)
        await self.resolve(source, branch(POSITION, PC, 1, wrong=True))
        await self.enable_tage(True)
        original = await self.capture_source(PC)
        return original, deepcopy(original.meta), self.common.source(original)

    async def consume_final_repair(self):
        await self.observation.wait('real_final_direction_repair_registered',
            lambda _: 'registered_tick' in self.common.proof.get('first_final-repair', {}))
        repair = self.common.proof['first_final-repair']
        await self.agent.set_ready(prediction=True, meta=True)
        while True:
            receipt = await self.agent.next_transaction(after_tick=repair['tick'])
            source = self.common.source(receipt)
            if source.token_sequence == repair['issued_token']:
                await self.pause()
                return receipt
            if source.token_sequence > repair['issued_token']:
                raise AssertionError('the exact lookup issued by the final repair was not publicly consumed')


@asynccontextmanager
async def final_iteration_program(agent, coverage):
    phr = BpuPhrChecker(scope='autonomous Main/TAGE/PHR and source-owned final IMLI direction repair')
    async with PipelineObservation(agent, sources=DirectionSources(), with_common_history=True,
            common_history_factory=LoopIterationChecks,
            common_history_binding_factory=loop_iteration_binding) as observation, agent.observe_phr(phr):
        common = observation.common; common.coverage = coverage
        await agent.reset(PC)
        anchor = await agent.next_transaction(start_pc=PC)
        common.register_anchor(anchor)
        await agent.set_ready(prediction=False, meta=True)
        await agent.configure_predictors(ubtb=False, abtb=False, mbtb=True, tage=False,
            sc=False, ittage=False, ras=False, settle=True)
        yield FinalIterationProgram(agent, observation, anchor, common)
        common.raise_failure(); phr.summary()
