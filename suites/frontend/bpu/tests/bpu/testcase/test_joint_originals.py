"""Sixteen cold/trained programs, without per-signal or asyncio plumbing."""
import pytest
from bpuverify.bpu.model.joint_originals import PROFILES
from bpuverify.bpu.coverage.joint_originals import Coverage
from bpuverify.bpu.case.joint_originals import check_joint_originals


@pytest.mark.feature('BPU-INT-107')
@pytest.mark.parametrize('profile',PROFILES)
async def test_adjacent_originals_complete_owned_direction_and_correction_learning(bpu_agent,bpu_sc_output,request,profile):
    coverage=Coverage(profile)
    try:await check_joint_originals(bpu_agent,profile,coverage)
    finally:
        coverage.write(bpu_sc_output);coverage.attach_evidence(request.node.user_properties)
