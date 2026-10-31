"""Concurrent stale sends use the production AsyncDriver, not case-level tasks."""
from suites.frontend.bpu.bpu.env.direction_migration import DirectionMigration
from suites.frontend.bpu.bpu.model.tage.migration import PC,POSITION,TARGET,PATHS
from suites.frontend.bpu.bpu.model.tage.stale_burst import SOURCE_COUNT
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback


class DirectionBurst(DirectionMigration):
    async def original_captured(self):
        self.checks.retain_source(self.checks.original)
        for _ in range(SOURCE_COUNT-1):
            self.checks.retain_source(await self.env.capture_via(PC,PATHS['original']))

    async def replay(self):
        events=await self.env.resolve_burst(tuple((source,(BpuBranchFeedback(POSITION,TARGET,1,taken=1,mispredict=0),))
            for source in self.checks.sources))
        self.checks.accepted(events)
        def serviced(_):
            self.monitor.raise_failure()
            return len(self.checks.written)==SOURCE_COUNT
        await self.env.observation.wait('all_stale_sources_retire_through_current_owner',serviced)
