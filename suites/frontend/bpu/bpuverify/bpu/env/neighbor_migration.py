"""Prepare real neighboring history, submit through production async driver."""
from bpuverify.bpu.env.dual_migration import prepare_dual_migration
from bpuverify.bpu.env.direction_service import DirectionService
from bpuverify.bpu.model.tage.neighbor_migration import PC


async def prepare_neighbor_migration(env, checks):
    await prepare_dual_migration(env, checks)
    enabled = True
    for step in checks.neighbor_intents:
        if enabled != step.enabled:
            await env.enable_tage(step.enabled)
            enabled = step.enabled
        before = await env.capture_via(PC, checks.history_paths[step.context])
        checks.neighbor_preparing(before, step)
        branches = env.branch_path(step.outcomes)
        event = (await env.resolve(before, *branches) if step.allocation is None else
                 await env.allocate(before, *branches, owner=step.allocation))
        after = await env.capture_via(PC, checks.history_paths[step.context])
        checks.neighbor_prepared(after, step, event)
        env.checker.retire_source(before.meta_tick)
        env.checker.retire_source(after.meta_tick)
    checks.arm_neighbor({name: await env.capture_via(PC, path) for name, path in checks.history_paths.items()})


class NeighborMigrationService(DirectionService):
    async def release(self):
        self.checks.release()
        await self.env.pause()
        def done(_):
            self.monitor.raise_failure()
            return tuple(len(self.checks.written[o]) for o in range(2)) == (self.checks.service_count,) * 2
        await self.env.observation.wait('both_neighbor_and_current_results_serviced', done)
        self.checks.services_complete()
