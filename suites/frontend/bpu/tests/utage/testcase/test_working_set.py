"""Logical lifetimes; drivers and monitors own every pipeline boundary."""
import pytest

from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.case.working_set import check_working_set
from bpuverify.utage.coverage.working_set import WorkingSetCoverage
from bpuverify.utage.model.working_set import MODES, SIZES, WorkingSetProgram


@pytest.mark.feature('BPU-UTAGE-020')
@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.parametrize('size', tuple(SIZES))
@pytest.mark.parametrize('mode', MODES)
async def test_history_working_set_retains_independent_learning_after_turnover(utage_agent, size, mode, request):
    program = WorkingSetProgram(size, mode)
    coverage = WorkingSetCoverage(program)
    try:
        await check_working_set(utage_agent, program, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
        coverage.attach_evidence(request.node.user_properties)
