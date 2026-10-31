"""Opposite correct feedback, partial visibility and full independent services."""
from suites.frontend.bpu.bpu.case.mixed_visibility import check_mixed_visibility
from suites.frontend.bpu.bpu.checker.direction_turnaround import DirectionTurnaroundChecks
from suites.frontend.bpu.bpu.env.direction_turnaround import prepare_direction_turnaround


async def check_direction_turnaround(agent,program,coverage):
    await check_mixed_visibility(agent,program,coverage,checks_factory=DirectionTurnaroundChecks,
                                 prepare=prepare_direction_turnaround)
