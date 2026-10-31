"""Reuse existing async drive, service monitoring and all consumer phases."""
from suites.frontend.bpu.bpu.case.direction_capacity import check_direction_capacity
from suites.frontend.bpu.bpu.checker.shared_saturation import Checks
from suites.frontend.bpu.bpu.bundle.shared_saturation import binding


async def check_shared_saturation(agent,program,coverage,evidence):
    await check_direction_capacity(agent,coverage,checks_factory=lambda pipeline,coverage:Checks(pipeline,coverage,program),
        binding_factory=binding,evidence=evidence)
