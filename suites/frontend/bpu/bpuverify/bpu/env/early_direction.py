"""Owned-source direction experiments; cases contain no clock/phase mechanics."""
from contextlib import asynccontextmanager

from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.env.branch_targets import BranchTargetProgram
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.early_direction_sources import EarlyDirectionSources
from bpuverify.bpu.transaction.types import BpuRedirect


class EarlyDirectionProgram(BranchTargetProgram):
    @property
    def fallback_position(self):return 4+(self.pc&8)

    @property
    def conditional_position(self):return 2+(self.pc&8)
    async def restart(self,source):
        await self.pause()
        self.checker.source_token(source)
        request=BpuRedirect(self.pc,source.meta.redirect,
            cfi_pc=(source.prediction.start_pc//16)*16+self.fallback_position,taken=1,branch_type=3)
        self.checker.plan_redirect(source,request)
        boundary=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        return boundary

    async def query(self,source):
        boundary=await self.restart(source)
        receipt=await self.agent.next_transaction(start_pc=self.pc,after_tick=boundary)
        self.checker.source_token(receipt)
        await self.pause()
        return receipt

    async def seed_ahead(self,source):
        boundary=await self.restart(source)
        await self.observation.wait('owned_ahead_write_waits_for_bank_service',lambda checker:
            any(bank.outstanding for bank in checker.model.sources.ahead.pending))
        latest=await self.agent.next_transaction(start_pc=self.pc,after_tick=boundary)
        self.checker.source_token(latest)
        await self.pause()
        await self.query(latest)
        await self.agent.set_ready(prediction=True,meta=True)
        return await self.consume('owned_ahead_conditional',lambda token:token.early.source=='ahead'
            and token.early.branch.position==self.conditional_position)

    async def consume(self,name,predicate):
        token=None
        def qualified(checker):
            nonlocal token
            cycle=checker.last_cycle
            candidate=None if cycle is None else cycle.metadata
            if candidate is not None and candidate.pc==self.pc and predicate(candidate):
                token=candidate
                return True
            return False
        await self.observation.wait(name,qualified,timeout_cycles=256)
        # The monitor can advance while wait delivery resumes this coroutine.
        # Keep the immutable accepted token, never re-read mutable last_cycle.
        boundary=self.checker.s1_accepts[token.sequence]-1
        receipt=await self.agent.next_transaction(start_pc=self.pc,after_tick=boundary)
        owned=self.checker.source_token(receipt)
        if not predicate(owned):raise AssertionError('receipt must retain the independently qualified source')
        await self.pause()
        return receipt

    async def consume_negative(self,source):
        await self.restart(source)
        def corrected(token):
            snapshot=self.checker.model.sources.short_snapshot(token)
            values=snapshot.prediction.values()
            return any(values.get(f'{way}.hit') and not values.get(f'{way}.taken') for way in range(4))
        return await self.consume('owned_short_history_negative_provider',corrected)


@asynccontextmanager
async def early_direction_program(agent,pc,checks,*,program_type=EarlyDirectionProgram,checker_factory=None):
    phr=BpuPhrChecker(scope='autonomous conditional Ahead/MicroTAGE/Main composition',record_limit=8)
    options={} if checker_factory is None else {'checker_factory':checker_factory}
    observation=PipelineObservation(agent,checks,sources=EarlyDirectionSources(),**options)
    checks.pipeline=observation.checker
    async with observation,agent.observe_phr(phr):
        await agent.reset(pc)
        anchor=await agent.next_transaction(start_pc=pc)
        await agent.configure_predictors(ubtb=False,abtb=True,mbtb=True,tage=False,sc=False,
            ittage=False,ras=False,settle=True)
        yield program_type(agent,observation,anchor,pc)
        phr.summary()
