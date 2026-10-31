"""Complete original execution prefixes under two learning lifecycle schedules."""
from suites.frontend.bpu.bpu.case.mixed_visibility import check_mixed_visibility
from suites.frontend.bpu.bpu.checker.interior_prefix_learning import Checks
from suites.frontend.bpu.bpu.env.interior_prefix_learning import LearningService
from suites.frontend.bpu.bpu.env.direction_turnaround import prepare_direction_turnaround


async def check_interior_prefix(agent,program,coverage,evidence):
    await check_mixed_visibility(agent,program,coverage,checks_factory=Checks,
        prepare=prepare_direction_turnaround,service_factory=LearningService,evidence=evidence)
