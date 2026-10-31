"""Queued old results wait while real younger loop predictions progress."""
import pytest
from suites.frontend.bpu.bpu.model.joint_stream import PROFILES
from suites.frontend.bpu.bpu.coverage.joint_stream import Coverage
from suites.frontend.bpu.bpu.case.joint_stream import check_joint_stream


@pytest.mark.feature('BPU-INT-107')
@pytest.mark.parametrize('profile',PROFILES)
async def test_waiting_old_results_preserve_both_learners_and_younger_predictions(bpu_agent,bpu_sc_output,request,profile):
    coverage=Coverage(profile)
    try:await check_joint_stream(bpu_agent,profile,coverage)
    finally:
        coverage.write(bpu_sc_output);coverage.attach_evidence(request.node.user_properties)
