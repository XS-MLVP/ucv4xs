"""Natural multi-branch lifetimes, separate from physical-coordinate sweeps."""
import pytest

from bpuverify.bpu.case.ahead_working_set import check_ahead_working_set
from bpuverify.bpu.coverage.ahead_working_set import AheadWorkingSetCoverage
from bpuverify.bpu.model.ahead_working_set import SIZES, KINDS, LIFETIMES, AheadWorkingSetProgram


@pytest.mark.feature('BPU-INT-100')
@pytest.mark.parametrize('size', tuple(SIZES))
@pytest.mark.parametrize('kinds', KINDS)
@pytest.mark.parametrize('lifetime', tuple(LIFETIMES))
async def test_natural_branch_working_set_retains_learning_and_reinitializes_new_identities(
        bpu_agent, bpu_sc_output, request, size, kinds, lifetime):
    program = AheadWorkingSetProgram(size, kinds, lifetime)
    coverage = AheadWorkingSetCoverage(program)
    try:
        await check_ahead_working_set(bpu_agent, program, coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)


from bpuverify.bpu.case.ahead_working_set import check_prefix_working_set
from bpuverify.bpu.coverage.ahead_working_set import PrefixWorkingSetCoverage
from bpuverify.bpu.model.ahead_working_set import PrefixWorkingSetProgram,PREFIX_PROFILES

# Measured on the 2026-10-21 full BPU program run; scheduling hint only.
pytestmark = pytest.mark.estimated_runtime(58)


@pytest.mark.feature('BPU-INT-056')
@pytest.mark.feature('BPU-INT-058')
@pytest.mark.feature('BPU-INT-059')
@pytest.mark.feature('BPU-INT-100')
@pytest.mark.parametrize('profile',PREFIX_PROFILES)
async def test_selected_condition_prefix_changes_without_forgetting_other_windows(bpu_agent,bpu_sc_output,request,profile):
    program=PrefixWorkingSetProgram(profile)
    coverage=PrefixWorkingSetCoverage(program)
    try:
        await check_prefix_working_set(bpu_agent,program,coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)
