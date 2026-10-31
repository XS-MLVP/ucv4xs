"""Useful service uses the existing AsyncDriver and SDK transfer monitors."""
from suites.frontend.bpu.bpu.bundle.tage_service import useful_service_binding
from suites.frontend.bpu.bpu.env.direction_service import DirectionService
from suites.frontend.bpu.bpu.model.tage.forwarding import PC
from suites.frontend.bpu.bpu.model.tage.useful_service import main_preparation


class DirectionUsefulService(DirectionService):
    def __init__(self,environment,checks):
        super().__init__(environment,checks,binding_factory=useful_service_binding)

    async def release(self):
        self.checks.release();await self.env.pause()
        def completed(_):
            self.monitor.raise_failure()
            return len(self.checks.written)==len(self.checks.plan)
        await self.env.observation.wait('all_actual_useful_service_receipts',completed)


async def prepare_useful_sources(environment,checks):
    await environment.prepare_direction_pair(checks.prepared)
    await environment.prepare_second_history(checks.prepared)
    await environment.enable_tage(False)
    for path,expected in main_preparation():
        source=await environment.capture_source(PC)
        await environment.resolve(source,*environment.branch_path(path))
        after=await environment.capture_source(PC);checks.prepared(after,expected)
        for old in (source,after):environment.checker.retire_source(old.meta_tick)
    await environment.enable_tage(True)
