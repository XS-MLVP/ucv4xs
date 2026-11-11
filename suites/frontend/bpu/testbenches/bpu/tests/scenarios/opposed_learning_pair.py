"""Paired correct old predictions share the existing full service lifetime."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.mixed_visibility import check_mixed_visibility
from suites.frontend.bpu.testbenches.bpu.checker.opposed_learning_pair import OpposedLearningPairChecks
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.direction_turnaround import prepare_direction_turnaround


async def check_opposed_learning_pair(agent,program,coverage,evidence):
    await check_mixed_visibility(agent,program,coverage,checks_factory=OpposedLearningPairChecks,
        prepare=prepare_direction_turnaround,evidence=evidence)
