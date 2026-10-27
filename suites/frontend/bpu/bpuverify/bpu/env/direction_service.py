"""Concurrent non-reread feedback; completion and SRAM retirement stay separate."""
from bpuverify.bpu.monitor.tage.service import TageServiceMonitor
from bpuverify.bpu.model.tage.service import STREAM_PC,STREAM_POSITION,learning_inflight
from bpuverify.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback,BpuRedirect


class DirectionService:
    def __init__(self,environment,checks,*,binding_factory=None):
        self.env,self.agent,self.checks=environment,environment.agent,checks
        self.monitor=TageServiceMonitor(self.agent,checks,binding_factory=binding_factory)

    async def __aenter__(self):
        await self.monitor.__aenter__()
        return self

    async def __aexit__(self,*exc):return await self.monitor.__aexit__(*exc)

    async def query(self,pc,*,via=None):
        """Replace the stream with a genuine checkpoint; never pause reads."""
        origin=self.env.anchor
        cfi=self.env.pc+4
        if via is not None:
            origin=await self.query(via)
            cfi=via+4
        boundary=await self.agent.redirect(BpuRedirect(pc,origin.meta.redirect,cfi_pc=cfi))
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        self.env.checker.source_token(source)
        self.monitor.raise_failure()
        return source

    async def start_stream(self):
        await self.query(getattr(self.checks,'stream_pc',STREAM_PC))
        self.checks.begin_read_window()

    async def submit(self,requests):
        requests=tuple(requests)
        transactions=[]
        for source,branches in requests:
            request=BpuBatchTraining(source.prediction.start_pc,source.meta.resolve,tuple(branches))
            self.env.checker.plan_feedback(source,request)
            transactions.append(request)
        before=self.env.checker.last_tick
        handles=tuple(self.agent.training_driver.send(request) for request in transactions)
        def healthy():
            self.monitor.raise_failure()
            return True
        try:
            await self.env.observation.wait('nonreread_concurrent_acceptance',
                lambda _:healthy() and all(handle.done() for handle in handles))
            ticks=tuple([(await handle).tick for handle in handles])
            receipts={tick:resolution for source,_ in requests
                for tick,resolution in self.env.checker.resolutions_for_source(source) if tick>before}
            actual=tuple(sorted(receipts.items()))
            self.checks.check(ticks,tuple(tick for tick,_ in actual),'all asynchronous sends have their exact compared acceptance')
            self.checks.accepted_burst(actual)
            await self.env.observation.wait('learning_mature_but_not_committed',
                lambda checker:healthy() and not learning_inflight(checker.model.sources.tage))
            self.checks.pending()
        finally:
            for handle in handles:
                if not handle.done() and handle.accepted_event is None:handle.cancel()

    async def release(self):
        self.checks.release()
        await self.env.pause()
        def completed(_):
            self.monitor.raise_failure()
            return tuple(len(self.checks.written[way]) for way in range(2))==(self.checks.program.retained_count,)*2
        await self.env.observation.wait('both_actual_sram_commit_receipts',completed)


async def prepare_service_stream(environment,*,pc=STREAM_PC):
    cold=await environment.capture_source(pc)
    await environment.resolve(cold,BpuBranchFeedback(STREAM_POSITION,pc,2,taken=1,mispredict=1))
    environment.checker.retire_source(cold.meta_tick)
