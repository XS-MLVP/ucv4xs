"""An older correction supersedes a still-pending younger correction."""
import pytest

from suites.frontend.bpu.testbenches.bpu.tests.scenarios.superseding_recovery import check_superseding_recovery
from suites.frontend.bpu.testbenches.bpu.coverage.superseding_recovery import SupersedingRecoveryCoverage
from suites.frontend.bpu.testbenches.bpu.model.superseding_recovery import SupersedingRecoveryProgram
from suites.frontend.bpu.testbenches.bpu.model.superseding_recovery import PROFILES


@pytest.mark.feature('BPU-INT-034')
@pytest.mark.feature('BPU-INT-043')
@pytest.mark.feature('BPU-INT-094')
@pytest.mark.feature('BPU-INT-099')
@pytest.mark.parametrize('profile', PROFILES)
async def test_older_original_supersedes_adjacent_younger_recovery(bpu_agent, bpu_sc_output, request, profile):
    coverage = SupersedingRecoveryCoverage()
    try:
        await check_superseding_recovery(bpu_agent, SupersedingRecoveryProgram(profile), coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)
