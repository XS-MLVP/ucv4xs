"""Normal old protection yields to a different branch without mixed identity."""
import pytest
from bpuverify.bpu.model.short_competition import Program,PROFILES
from bpuverify.bpu.coverage.short_competition import Coverage
from bpuverify.bpu.case.short_competition import check_competition

# Measured on the 2026-10-21 full BPU program run; scheduling hint only.
pytestmark = pytest.mark.estimated_runtime(128)


@pytest.mark.feature('BPU-INT-104')
@pytest.mark.parametrize('profile',PROFILES)
async def test_protected_short_experience_yields_to_new_branch_without_borrowed_confidence(bpu_agent,bpu_sc_output,request,profile):
    program=Program(profile);coverage=Coverage(program)
    try:await check_competition(bpu_agent,program,coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)
