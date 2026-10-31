"""Normal feedback, original-source lifetime and SDK-confirmed redirected writes."""
from suites.frontend.bpu.bpu.model.tage.migration import PC,POSITION,TARGET,PATHS
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.monitor.tage.service import TageServiceMonitor


class DirectionMigration:
    def __init__(self,environment,checks):
        self.env,self.checks=environment,checks
        self.monitor=None

    async def prepare(self):
        enabled=True
        for intent in self.checks.intents:
            if enabled!=intent.tage_enabled:
                await self.env.enable_tage(intent.tage_enabled);enabled=intent.tage_enabled
            source=await self.env.capture_via(PC,PATHS[intent.context])
            self.checks.preparing_input(source,intent)
            branch=BpuBranchFeedback(POSITION,TARGET,1,taken=int(intent.taken),mispredict=int(intent.wrong))
            event=await self.env.resolve(source,branch) if intent.owner is None else await self.env.allocate(source,branch,owner=intent.owner)
            after=await self.env.capture_via(PC,PATHS[intent.context])
            self.checks.prepared(after,intent,event)
            if intent.label=='original':await self.original_captured()
            self.env.checker.retire_source(source.meta_tick)
            if intent.label!='original':self.env.checker.retire_source(after.meta_tick)

    async def original_captured(self):
        """A profile may retain more genuine old predictions before migration."""

    async def profile(self):
        return {name:await self.env.capture_via(PC,path) for name,path in PATHS.items()}

    def observe(self):
        if self.monitor is not None:raise RuntimeError('delayed-source observation is single-use')
        self.monitor=TageServiceMonitor(self.env.agent,self.checks)
        return self.monitor

    async def replay(self):
        event=await self.env.resolve(self.checks.original,BpuBranchFeedback(POSITION,TARGET,1,taken=1,mispredict=0))
        self.checks.accepted(event)
        def serviced(_):
            self.monitor.raise_failure()
            return len(self.checks.written)==1
        await self.env.observation.wait('delayed_source_current_owner_commit',serviced)
