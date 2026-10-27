"""Paired correct old predictions share the existing full service lifetime."""
from bpuverify.bpu.case.mixed_visibility import check_mixed_visibility
from bpuverify.bpu.checker.opposed_learning_pair import OpposedLearningPairChecks
from bpuverify.bpu.env.direction_turnaround import prepare_direction_turnaround


async def check_opposed_learning_pair(agent,program,coverage,evidence):
    await check_mixed_visibility(agent,program,coverage,checks_factory=OpposedLearningPairChecks,
        prepare=prepare_direction_turnaround,evidence=evidence)
