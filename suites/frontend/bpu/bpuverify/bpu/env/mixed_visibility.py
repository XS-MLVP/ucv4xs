"""Semantic windows reuse the existing receipt-terminated SDK service driver."""
from functools import partial

from bpuverify.bpu.bundle.partial_residency import partial_residency_binding
from bpuverify.bpu.env.asymmetric_retirement import prepare_asymmetric_retirement
from bpuverify.bpu.env.partial_reuse import PartialReuseService
from bpuverify.bpu.model.tage.asymmetric_retirement import OUTCOMES
from bpuverify.bpu.model.tage.neighbor_migration import PC


async def prepare_mixed_visibility(env, checks):
    await prepare_asymmetric_retirement(env, checks)
    if 'old-neighbor' in checks.program.late_sources:
        checks.save_old_neighbor(await env.capture_via(PC, checks.history_paths['neighbor']))


class MixedVisibilityService(PartialReuseService):
    def __init__(self, env, checks, *, binding_factory=None):
        factory=(partial(partial_residency_binding, include_hit_ranks=True)
                 if binding_factory is None else binding_factory)
        super().__init__(env, checks, binding_factory=factory)

    async def submit_prelude(self):
        await self.submit(tuple((s, self.env.branch_path(o))
            for s, o in zip(self.checks.requests[:3], OUTCOMES[:3], strict=True)))

    async def submit_mixed_learning(self):
        self.checks.arm_mixed()
        await self.submit(tuple((s, self.env.branch_path(o))
            for s, o in zip(self.checks.requests[3:], self.checks.program.late_outcomes, strict=True)))

    async def release(self):
        self.checks.release()
        await self.env.pause()
        def completed(_):
            self.monitor.raise_failure()
            return tuple(map(len, self.checks.written.values())) == tuple(1 + len(p) for p in self.checks.expected_plan)
        await self.env.observation.wait('independent_mixed_visibility_services_complete', completed)
        self.checks.services_complete()
