"""Normal asynchronous driver admission and existing SDK service observation."""
from suites.frontend.bpu.bpu.env.dual_migration import prepare_dual_migration
from suites.frontend.bpu.bpu.model.tage.dual_retirement import PC, PATHS, OUTCOMES, SOURCE_COUNT
from suites.frontend.bpu.bpu.monitor.tage.service import TageServiceMonitor


class DualRetirementProgram:
    def __init__(self, env, checks):
        self.env, self.checks, self.monitor = env, checks, None

    async def prepare(self):
        await prepare_dual_migration(self.env, self.checks)

    def observe(self):
        if self.monitor is not None:
            raise RuntimeError('dual-retirement observation is single-use')
        self.monitor = TageServiceMonitor(self.env.agent, self.checks)
        return self.monitor

    async def replay(self):
        self.checks.begin_burst()
        events = await self.env.resolve_burst(tuple((s, self.env.branch_path(OUTCOMES)) for s in self.checks.sources))
        self.checks.accepted_burst(events)
        def done(_):
            self.monitor.raise_failure()
            return tuple(len(self.checks.written[o]) for o in range(2)) == (SOURCE_COUNT,) * 2
        await self.env.observation.wait('all_dual_successors_actually_serviced', done)
        self.checks.services_complete()

    async def profile(self):
        return {name: await self.env.capture_via(PC, path) for name, path in PATHS.items()}
