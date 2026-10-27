"""Four semantic confidence trajectories over existing driver/monitor scopes."""
from bpuverify.bpu.case.mixed_visibility import check_mixed_visibility
from bpuverify.bpu.checker.confidence_boundary import ConfidenceBoundaryChecks
from bpuverify.bpu.env.direction_turnaround import prepare_direction_turnaround
from bpuverify.bpu.env.confidence_boundary import ConfidenceBoundaryService


async def check_confidence_boundary(agent,program,coverage,*,traffic='returning'):
    factory=lambda pipeline,coverage,program:ConfidenceBoundaryChecks(pipeline,coverage,program,traffic=traffic)
    await check_mixed_visibility(agent,program,coverage,checks_factory=factory,
                                 prepare=prepare_direction_turnaround,service_factory=ConfidenceBoundaryService)
