"""Opposite correct feedback, partial visibility and full independent services."""
from bpuverify.bpu.case.mixed_visibility import check_mixed_visibility
from bpuverify.bpu.checker.direction_turnaround import DirectionTurnaroundChecks
from bpuverify.bpu.env.direction_turnaround import prepare_direction_turnaround


async def check_direction_turnaround(agent,program,coverage):
    await check_mixed_visibility(agent,program,coverage,checks_factory=DirectionTurnaroundChecks,
                                 prepare=prepare_direction_turnaround)
