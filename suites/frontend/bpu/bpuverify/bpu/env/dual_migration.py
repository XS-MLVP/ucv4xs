"""Normal history paths and production driver/monitor service; no case tasks."""
from bpuverify.bpu.env.direction_service import DirectionService, prepare_service_stream
from bpuverify.bpu.model.tage.dual_migration import PC, PATHS, OUTCOMES, preparation


class DualMigrationService(DirectionService):
    async def release(self):
        self.checks.release()
        await self.env.pause()
        def done(_):
            self.monitor.raise_failure()
            return tuple(len(self.checks.written[w]) for w in range(2)) == (1, 1)
        await self.env.observation.wait('both_swapped_owner_results_serviced', done)

    async def reactivate(self):
        self.checks.begin_clean()
        event = await self.env.resolve(self.checks.sources[2], *self.env.branch_path(OUTCOMES))
        self.checks.accepted_clean(event)
        def done(_):
            self.monitor.raise_failure()
            return tuple(len(self.checks.written[w]) for w in range(2)) == (2, 2)
        await self.env.observation.wait('both_clean_swapped_owners_serviced', done)


async def prepare_dual_migration(env, checks):
    await prepare_service_stream(env)
    enabled = True
    for step in preparation():
        if enabled != step.enabled:
            await env.enable_tage(step.enabled)
            enabled = step.enabled
        before = await env.capture_via(PC, PATHS[step.context])
        checks.preparing_input(before, step)
        branches = env.branch_path(step.outcomes)
        event = (await env.resolve(before, *branches) if step.allocation is None else
                 await env.allocate(before, *branches, owner=step.allocation))
        after = await env.capture_via(PC, PATHS[step.context])
        checks.prepared(after, step, event)
        env.checker.retire_source(before.meta_tick)
        if step.save:
            checks.retain_old(after)
            for _ in range(checks.source_count - 1):
                checks.retain_old(await env.capture_via(PC, PATHS['original']))
        else:
            env.checker.retire_source(after.meta_tick)
    current = {name: await env.capture_via(PC, path) for name, path in PATHS.items()}
    checks.arm(current)
