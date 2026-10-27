"""Complete shared outcome lifecycles, not signal-level test plumbing."""
import pytest
from bpuverify.bpu.model.joint_direction_learning import PROFILES
from bpuverify.bpu.coverage.joint_direction_learning import Coverage
from bpuverify.bpu.case.joint_direction_learning import check_joint_learning


@pytest.mark.feature('BPU-INT-106')
@pytest.mark.parametrize('profile',PROFILES)
async def test_one_loop_outcome_completes_both_direction_and_correction_learning(bpu_agent,bpu_sc_output,request,profile):
    coverage=Coverage(profile)
    try:await check_joint_learning(bpu_agent,profile,coverage)
    finally:
        coverage.write(bpu_sc_output);coverage.attach_evidence(request.node.user_properties)
