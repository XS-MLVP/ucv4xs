"""Late original loop learning, observed through fresh numerical consumers."""
import pytest
from bpuverify.bpu.model.sc_loop_experience import PROFILES
from bpuverify.bpu.coverage.sc_loop_experience import Coverage
from bpuverify.bpu.case.sc_loop_experience import check_loop_experience


@pytest.mark.feature('BPU-INT-105')
@pytest.mark.parametrize('profile',PROFILES)
async def test_old_loop_outcome_learns_its_original_iteration_while_younger_predictions_advance(bpu_agent,bpu_sc_output,request,profile):
    coverage=Coverage(profile)
    try:await check_loop_experience(bpu_agent,profile,coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)
