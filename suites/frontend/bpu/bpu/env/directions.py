"""Atomic normal-driver admission from owned TAGE allocation forecasts."""
from contextlib import asynccontextmanager
from toffee import CheckContext,ScoreboardMode

from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.env.branch_targets import BranchTargetProgram
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.model.direction_sources import DirectionSources
from suites.frontend.bpu.bpu.model.pipeline import Resolution,Outcome
from suites.frontend.bpu.bpu.model.selection import Kind,StackAction
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback,BpuRedirect
from suites.frontend.bpu.bpu.model.tage.forwarding import PC,POSITIONS,TARGETS,establish_program


class DirectionProgram(BranchTargetProgram):
    @staticmethod
    def branch_path(program):
        return tuple(BpuBranchFeedback(POSITIONS[index],TARGETS[index],1,taken=int(taken),mispredict=int(wrong))
            for index,taken,wrong in program)

    async def prepare_direction_pair(self,verify):
        """Reusable real-source setup for two opposed longest-history owners."""
        for operation,path,owner,expected in establish_program():
            if operation in ('disable','enable'):
                await self.enable_tage(operation=='enable')
                continue
            source=await self.capture_source(PC)
            if operation=='allocate':await self.allocate(source,*self.branch_path(path),owner=owner)
            else:await self.resolve(source,*self.branch_path(path))
            after=await self.capture_source(PC)
            verify(after,expected)
            self.checker.retire_source(source.meta_tick)
            self.checker.retire_source(after.meta_tick)

    async def capture_via(self,pc,via):
        intermediate=await self.capture_source(via)
        await self.pause()
        boundary=await self.agent.redirect(BpuRedirect(pc,intermediate.meta.redirect,cfi_pc=via+4))
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        self.checker.source_token(source)
        await self.pause()
        self.checker.retire_source(intermediate.meta_tick)
        return source

    async def prepare_second_history(self,verify):
        from suites.frontend.bpu.bpu.model.tage.service import VIA_PC
        await self.prepare_direction_history(VIA_PC,verify)

    async def prepare_direction_history(self,via,verify):
        from suites.frontend.bpu.bpu.model.tage.service import secondary_program
        for operation,path,owner,expected in secondary_program():
            if operation in ('disable','enable'):
                await self.enable_tage(operation=='enable')
                continue
            source=await self.capture_via(PC,via)
            if operation=='allocate':await self.allocate(source,*self.branch_path(path),owner=owner)
            else:await self.resolve(source,*self.branch_path(path))
            after=await self.capture_via(PC,via)
            verify(after,expected)
            self.checker.retire_source(source.meta_tick)
            self.checker.retire_source(after.meta_tick)

    async def resolve(self,source,*branches):
        # The domain checker releases the old owner only after its new
        # public consumer has compared successfully, not at driver return.
        return await super().resolve(source,*branches,retire=False)

    async def resolve_burst(self,requests):
        """Register every original owner, submit all inputs, then await effects.

        Requests are (public source, complete semantic branch prefix) pairs.
        The production AsyncDriver owns concurrency and acceptance; the case
        never handles tasks or queues. Keep owners until checked consumers.
        """
        requests=tuple(requests)
        if not requests:raise ValueError('owned feedback burst requires at least one request')
        await self.pause()
        transactions=[]
        for source,branches in requests:
            transaction=BpuBatchTraining(source.prediction.start_pc,source.meta.resolve,tuple(branches))
            self.checker.plan_feedback(source,transaction)
            transactions.append(transaction)
        before=self.checker.last_tick
        ticks=await self.agent.train_batches(tuple(transactions))
        await self.pause()
        self.checker.raise_failure()
        # Resolve from exact live owners, not a bounded diagnostic ring or
        # nearby PC/history matches. Reused sources may own several events.
        accepted={tick:resolution for source,_ in requests
            for tick,resolution in self.checker.resolutions_for_source(source) if tick>before}
        actual=tuple(sorted(accepted.items()))
        self.checker.board.check(expected=ticks,actual=tuple(tick for tick,_ in actual),
            context=CheckContext(self.checker.board.name,ScoreboardMode.DIRECT,
                request=dict(point='each burst input has one compared acceptance',requests=requests)))
        return actual

    async def allocate(self,source,*branches,owner,timeout_cycles=1823):
        if type(timeout_cycles) is not int or timeout_cycles<=0:
            raise ValueError('allocation timeout must be a positive cycle budget')
        await self.pause()
        token = self.checker.source_token(source)
        resolution = Resolution(token.history,token.pc,tuple(Outcome(branch.position,branch.target,
            Kind(branch.branch_type),bool(branch.taken),StackAction(branch.ras_action),bool(branch.mispredict))
            for branch in branches)+(None,)*(8-len(branches)),origin=token)
        feedback = self.checker.model.sources.feedback_for(resolution)
        before,attempts = None,0
        def admit(transaction):
            nonlocal before,attempts
            self.checker.raise_failure()
            attempts += 1
            candidate = self.checker.model.sources.tage.allocation_at_next_accept(feedback)
            if candidate is None:raise ValueError('owned source has no eligible longer-history allocation')
            if candidate==owner:
                before = self.checker.last_tick
                return True
            if attempts>=timeout_cycles:
                raise TimeoutError(f'owned TAGE allocation: owner={owner}, candidate={candidate}, '
                    f'tick={self.checker.last_tick}, drive_opportunities={attempts}')
            return False
        with self.agent.training_driver.admit_when(admit):
            actual = await self.resolve(source,*branches)
        self.checker.board.check(expected=(before+2,resolution),actual=actual,
            context=CheckContext(self.checker.board.name,ScoreboardMode.DIRECT,
                request=dict(point='owned next-accept allocation forecast',owner=owner,forecast_tick=before)))
        return actual

    async def enable_tage(self,enabled):
        # Stop older work before changing CSR. The next capture redirects,
        # squashing the held S1 from the old enable epoch before consumption.
        await self.pause()
        await self.agent.configure_predictors(tage=enabled,settle=True)


@asynccontextmanager
async def direction_program(agent,pc,*,sources_factory=DirectionSources):
    phr = BpuPhrChecker(scope='autonomous MicroBTB/MainBTB/TAGE with exact request-owned feedback')
    async with PipelineObservation(agent,sources=sources_factory()) as observation,agent.observe_phr(phr):
        await agent.reset(pc)
        anchor = await agent.next_transaction(start_pc=pc)
        await agent.set_ready(prediction=False,meta=True)
        await agent.configure_predictors(ubtb=False,abtb=False,mbtb=True,tage=True,sc=False,
            ittage=False,ras=False,settle=True)
        yield DirectionProgram(agent,observation,anchor,pc)
        phr.summary()
