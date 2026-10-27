"""Normal learning and a public driver burst; no testcase clock choreography."""
from contextlib import asynccontextmanager
from functools import partial

from bpuverify.bpu.bundle.common_query import common_query_binding
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.checker.superseding_recovery import SupersedingRecoveryChecks
from bpuverify.bpu.env.common_history import CommonProgram, prepare
from bpuverify.bpu.env.main_service import branch
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.common_history import LOOKUP_WINDOW_CAPACITY
from bpuverify.bpu.model.main_sources import BranchTargetSources
from bpuverify.bpu.model.superseding_recovery import PC, BACKWARD, RULES
from bpuverify.bpu.transaction.types import BpuRedirect


class SupersedingRecoveryEnv(CommonProgram):
    async def run_pair(self, program):
        await prepare(self, later_conditional=False)
        source = await self.capture_source(BACKWARD)
        await self.resolve(source, branch(5, BACKWARD, 2, wrong=True))
        request = BpuRedirect(PC, self.anchor.meta.redirect, cfi_pc=PC+4)
        self.checker.plan_redirect(self.anchor, request)
        self.common.plan(self.anchor, request)
        tick = await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True, meta=True)
        while True:
            older = await self.agent.next_transaction(start_pc=PC, after_tick=tick)
            original = self.common.source(older)
            if original.count >= 2*LOOKUP_WINDOW_CAPACITY:
                break
        younger = await self.agent.next_transaction(start_pc=PC, after_tick=older.prediction_tick)
        await self.pause()
        self.common.arm(older, younger)
        requests = []
        for receipt, correction in ((younger, program.younger), (older, program.older)):
            request = BpuRedirect(correction.target, receipt.meta.redirect,
                cfi_pc=PC+correction.position, taken=int(correction.taken), branch_type=int(correction.kind))
            self.checker.plan_redirect(receipt, request)
            self.common.plan(receipt, request)
            requests.append(request)
        ticks = await self.agent.redirect_many(requests)
        self.common.accepted_pair(ticks)
        await self.observation.wait('older_recovery_complete_without_younger_prefix',
            lambda _: self.common.final_state is not None)
        await self.agent.set_ready(prediction=True, meta=True)
        while True:
            receipt = await self.agent.next_transaction(start_pc=program.consumer_pc, after_tick=ticks[-1])
            self.common.raise_failure()
            token = self.checker.source_token(receipt)
            source = self.common.query.snapshot(token)
            if source.published and source.metadata.valid:
                break
        await self.pause()
        self.common.consumed_winner(receipt)


@asynccontextmanager
async def superseding_recovery_env(agent, program, coverage):
    phr = BpuPhrChecker(scope='two adjacent published-source recoveries; younger then surviving older', record_limit=16)
    async with PipelineObservation(agent, sources=BranchTargetSources(), with_common_history=True,
            common_history_factory=partial(SupersedingRecoveryChecks, program=program, coverage=coverage),
            common_history_binding_factory=common_query_binding) as observation, agent.observe_phr(phr):
        await agent.reset(PC)
        anchor = await agent.next_transaction(start_pc=PC)
        common = observation.common
        common.register_anchor(anchor)
        await agent.configure_predictors(ubtb=True, abtb=False, mbtb=True, tage=False,
                                        sc=False, ittage=False, ras=False, settle=True)
        yield SupersedingRecoveryEnv(agent, observation, anchor, common)
        common.raise_failure()
        phr.summary()
