"""Bounded source acquisition; no tests drive edges or know picker phases."""
from contextlib import asynccontextmanager
from copy import deepcopy

from suites.frontend.bpu.bpu.driver.control import PredictionWindow
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.model.main_sources import BranchTargetSources
from suites.frontend.bpu.bpu.model.main_service import PC,STREAM_PC
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuRedirect
from suites.frontend.bpu.monitors.activity import TRAINING_TIMEOUT_CYCLES
from suites.frontend.bpu.bpu.checker.bounded_sources import BoundedChecker
from suites.frontend.bpu.bpu.env.feedback_gate import FeedbackProgram
from suites.frontend.bpu.bpu.bundle.bounded_sources import binding


class BoundedObservation(PipelineObservation):
    def __init__(self,agent,*,capacity=8,simultaneous_training_recovery=False):
        super().__init__(agent,sources=BranchTargetSources(),binding_factory=binding)
        self.checker=BoundedChecker(capacity=capacity,
            simultaneous_training_recovery=simultaneous_training_recovery)


class BoundedProgram(FeedbackProgram):
    async def accept_window(self,pc,*,quota=1):
        ledger=self.checker.windows.ledger
        window=self.checker.selection.arm(pc,quota,available=ledger.capacity-len(ledger.active),requires_preparation=False)
        try:
            event=await self.agent.control_driver.send(PredictionWindow(
                self.agent._control_values(),window.accepted,'bounded-original-S1-window',
                TRAINING_TIMEOUT_CYCLES,lambda:self.checker.failure))
            return self.checker.selection.finish(window,event)
        finally:self.checker.selection.cancel(window)

    async def capture(self,pc,verify):
        await self.pause()
        self.checker.windows.ledger.live(self.checker.receipt_window(self.anchor))
        request=BpuRedirect(pc,self.anchor.meta.redirect,cfi_pc=self.anchor.prediction.start_pc+1)
        self.checker.plan_redirect(self.anchor,request)
        boundary=await self.agent.redirect(request)
        before=self.checker.windows.counts['S1-admission']
        receipts=await self.accept_window(pc)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        verify(source)
        assert receipts==((source.prediction_tick,self.checker.source_token(source).sequence),)
        await self.pause()
        assert self.checker.windows.counts['S1-admission']==before+1
        self.anchor=source
        return source

    def prepare_feedback(self,source,*branches):
        tx=BpuBatchTraining(source.prediction.start_pc,deepcopy(source.meta.resolve),tuple(branches))
        self.checker.gate.prepare(self.checker.receipt_window(source),tx,receipt_metadata=source.meta.resolve)
        return tx

    async def send_input(self,source,tx,*,drain=True):
        def admit(transaction):
            self.checker.raise_failure()
            self.checker.gate.admit(transaction)
            self.checker.plan_feedback(source,transaction)
            return True
        with self.agent.training_driver.admit_when(admit):
            handle=self.agent.training_driver.send(tx)
            self.submissions.append(handle)
            event=await handle
        self.checker.raise_failure()
        assert self.checker.actual_inputs[-1]['tick']==event.tick
        if drain:await self.pause()
        return event

    async def teach(self,source,*branches):
        return await self.send_input(source,self.prepare_feedback(source,*branches))

    async def send_input_and_recover(self,source,tx,owner,request):
        """Two existing public drivers; the monitor must certify one boundary.

        No phase/edge knowledge is exposed to cases. Submitting training is
        immediate; the awaited redirect leaves its driver and the queued
        training driver running concurrently. Equal actual acceptance ticks,
        not Python task launch order, establish the promised coincidence.
        """
        if not self.checker.simultaneous_training_recovery:
            raise RuntimeError('same-boundary training/recovery contract was not enabled')
        def admit(transaction):
            self.checker.raise_failure()
            self.checker.gate.admit(transaction)
            self.checker.plan_feedback(source,transaction)
            return True
        self.checker.plan_redirect(owner,request)
        with self.agent.training_driver.admit_when(admit):
            handle=self.agent.training_driver.send(tx)
            self.submissions.append(handle)
            recovery_tick=await self.agent.redirect(request)
            accepted=await handle
        self.checker.raise_failure()
        if accepted.tick!=recovery_tick:
            raise AssertionError(f'drivers did not accept on one boundary: training={accepted.tick}, recovery={recovery_tick}')
        return accepted,recovery_tick


@asynccontextmanager
async def bounded_program(agent,*,late_enabled_at_boot=True,capacity=8,simultaneous_training_recovery=False):
    phr=BpuPhrChecker(scope='bounded real-source Main sibling preservation')
    async with BoundedObservation(agent,capacity=capacity,
            simultaneous_training_recovery=simultaneous_training_recovery) as observation,agent.observe_phr(phr):
        # Controls are fixed while the factory's reset is still asserted, so
        # the FIRST helper owns an enabled Main read frame. No extra helper
        # occurrence or invented commit is needed to make room for old work.
        await agent.set_ready(prediction=False,meta=True)
        await agent.configure_predictors(ubtb=True,abtb=False,mbtb=True,tage=late_enabled_at_boot,
            sc=False,ittage=False,ras=False,settle=True)
        await agent.reset(STREAM_PC)
        env=BoundedProgram(agent,observation,None,STREAM_PC)
        receipts=await env.accept_window(STREAM_PC)
        anchor=await agent.next_transaction(start_pc=STREAM_PC,after_tick=receipts[0][0]-1)
        assert observation.checker.source_token(anchor).sequence==receipts[0][1]
        env.anchor=anchor
        await env.pause()
        if late_enabled_at_boot:
            # This is an explicit scenario distinction, not an unreported
            # warm-up workaround: a separate DUT case retains cold-disabled
            # isolation and must fail if disabled outputs influence Main.
            await agent.configure_predictors(tage=False,settle=True)
        yield env,anchor
        phr.summary()
