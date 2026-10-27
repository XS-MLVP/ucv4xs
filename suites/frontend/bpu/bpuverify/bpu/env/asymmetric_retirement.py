"""Two semantic bursts, one uninterrupted read window; existing SDK async driver."""
from functools import partial

from bpuverify.bpu.bundle.partial_residency import partial_residency_binding
from bpuverify.bpu.env.neighbor_migration import prepare_neighbor_migration, NeighborMigrationService
from bpuverify.bpu.model.tage.asymmetric_retirement import OUTCOMES
from bpuverify.bpu.model.tage.neighbor_migration import PC


async def prepare_asymmetric_retirement(env, checks):
    await prepare_neighbor_migration(env, checks)
    source = await env.capture_via(PC, checks.history_paths['original'])
    event = await env.resolve(source, *env.branch_path(OUTCOMES[1]))
    current = {name: await env.capture_via(PC, path) for name, path in checks.history_paths.items()}
    checks.arm_asymmetric(source, event, current)
    env.checker.retire_source(source.meta_tick)


class AsymmetricRetirementService(NeighborMigrationService):
    def __init__(self, env, checks):
        super().__init__(env, checks, binding_factory=partial(partial_residency_binding, include_hit_ranks=True))

    async def submit_prelude(self):
        await self.submit(tuple((s, self.env.branch_path(o))
            for s, o in zip(self.checks.requests[:3], OUTCOMES[:3], strict=True)))

    async def submit_late_learning(self):
        await self.submit(tuple((s, self.env.branch_path(o))
            for s, o in zip(self.checks.requests[3:], OUTCOMES[3:], strict=True)))
