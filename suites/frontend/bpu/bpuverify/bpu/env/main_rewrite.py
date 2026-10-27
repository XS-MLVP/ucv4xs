"""Reuse owned Main port monitors and production async driver; no case tasks."""
from bpuverify.bpu.env.main_service import MainService,branch
from bpuverify.bpu.model.main_rewrite import PC,POSITION,TARGETS
from bpuverify.bpu.transaction.types import BpuBatchTraining


class MainRewriteService(MainService):
    async def submit(self,sources):
        transactions=[]
        for source,target in zip(sources,TARGETS[:2],strict=True):
            tx=BpuBatchTraining(PC,source.meta.resolve,(branch(POSITION,target,3,wrong=True),))
            self.env.checker.plan_feedback(source,tx);transactions.append(tx)
        before=self.env.checker.last_tick
        handles=tuple(self.agent.training_driver.send(tx) for tx in transactions)
        def healthy():self.monitor.raise_failure();return True
        try:
            await self.env.observation.wait('main_complete_versions_accepted',lambda _:healthy() and all(h.done() for h in handles))
            ticks=tuple([(await h).tick for h in handles])
            accepted=tuple(sorted({tick:r for source in sources for tick,r in self.env.checker.resolutions_for_source(source)
                if tick>before}.items()))
            self.checks.check(ticks,tuple(t for t,_ in accepted),'all send handles retain their exact original acceptances')
            self.checks.accepted_burst(accepted)
            await self.env.observation.wait('main_complete_versions_mature',lambda c:healthy()
                and c.model.sources.main.offered is None and not any(c.model.sources.main.entry_offers.values()))
            self.checks.pending()
        finally:
            for h in handles:
                if not h.done() and h.accepted_event is None:h.cancel()

    async def release(self):
        self.checks.release();await self.env.pause()
        def done(_):self.monitor.raise_failure();return tuple(map(len,self.checks.written))==(1,0,2)
        await self.env.observation.wait('main_latest_complete_version_serviced',done)

    async def reactivate(self,source):
        self.checks.reactivate(source)
        await self.env.resolve(source,branch(POSITION,TARGETS[2],3,wrong=True),retire=False)
        def done(_):self.monitor.raise_failure();return tuple(map(len,self.checks.written))==(2,0,3)
        await self.env.observation.wait('main_clean_complete_version_serviced',done)
