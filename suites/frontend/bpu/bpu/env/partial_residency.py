"""Actual old-source inputs and single-owner services over existing SDK drivers."""
from suites.frontend.bpu.bpu.bundle.partial_residency import partial_residency_binding
from suites.frontend.bpu.bpu.env.direction_service import DirectionService, prepare_service_stream
from suites.frontend.bpu.bpu.model.tage.partial_residency import PC, PATHS


async def prepare_partial_residency(env, checks):
    await prepare_service_stream(env)
    enabled = True
    for step in checks.intents:
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
        names = checks.program.capture_names(step)
        if not names:
            env.checker.retire_source(after.meta_tick)
        for index, name in enumerate(names):
            source = after if index == 0 else await env.capture_via(PC, PATHS['original'])
            checks.save_source(name, source)
    checks.arm({name: await env.capture_via(PC, path) for name, path in PATHS.items()})


class PartialResidencyService(DirectionService):
    def __init__(self, env, checks):
        super().__init__(env, checks, binding_factory=partial_residency_binding)

    async def submit_stage(self):
        await self.submit(tuple((self.checks.saved[name], self.env.branch_path(outcomes))
            for name, outcomes in zip(self.checks.stage.sources, self.checks.stage.outcomes, strict=True)))

    async def release(self):
        self.checks.release()
        await self.env.pause()
        def completed(_):
            self.monitor.raise_failure()
            return tuple(map(len, self.checks.written.values())) == tuple(map(len, self.checks.expected_plan))
        await self.env.observation.wait('exact_single_owner_residency_service', completed)
        self.checks.services_complete()
