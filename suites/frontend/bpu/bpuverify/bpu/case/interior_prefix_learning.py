"""Complete original execution prefixes under two learning lifecycle schedules."""
from bpuverify.bpu.case.mixed_visibility import check_mixed_visibility
from bpuverify.bpu.checker.interior_prefix_learning import Checks
from bpuverify.bpu.env.interior_prefix_learning import LearningService
from bpuverify.bpu.env.direction_turnaround import prepare_direction_turnaround


async def check_interior_prefix(agent,program,coverage,evidence):
    await check_mixed_visibility(agent,program,coverage,checks_factory=Checks,
        prepare=prepare_direction_turnaround,service_factory=LearningService,evidence=evidence)
