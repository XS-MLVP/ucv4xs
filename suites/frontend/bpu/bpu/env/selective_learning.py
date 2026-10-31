"""Public transactions and event-based completion for selective learning."""
from suites.frontend.bpu.bpu.env.direction_service import DirectionService
from suites.frontend.bpu.bpu.model.tage.forwarding import PC
from suites.frontend.bpu.bpu.model.tage.selective_learning import preparation


async def capture(environment, path):
    return await environment.capture_source(PC) if path is None else await environment.capture_via(PC, path)


async def prepare(environment, checks):
    await environment.prepare_direction_pair(checks.prepared)
    for path in checks.program.paths[1:]:
        await environment.prepare_direction_history(path, checks.prepared)
    for path in checks.program.paths:
        enabled = True
        for learning, outcome, expected in preparation(checks.program.direction):
            if enabled != learning:
                await environment.enable_tage(learning)
                enabled = learning
            source = await capture(environment, path)
            await environment.resolve(source, *environment.branch_path(outcome))
            after = await capture(environment, path)
            checks.prepared(after, expected)
            environment.checker.retire_source(source.meta_tick)
            environment.checker.retire_source(after.meta_tick)
        await environment.enable_tage(True)
        source = await capture(environment, path)
        checks.prepared(source, ((0, 3), checks.program.initial))
        environment.checker.retire_source(source.meta_tick)


class LearningService(DirectionService):
    async def send_indices(self, indices):
        self.checks.begin_batch(indices)
        await self.submit(tuple((self.checks.sources[i], self.env.branch_path(self.checks.program.outcome)) for i in indices))

    async def release(self):
        self.checks.release()
        await self.env.pause()
        def complete(_):
            self.monitor.raise_failure()
            return self.checks.wave_serviced()
        await self.env.observation.wait('all_and_only_qualified_branch_services', complete)
        self.checks.services_complete()
