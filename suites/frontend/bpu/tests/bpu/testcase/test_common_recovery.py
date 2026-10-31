"""Actual CFI kind and direction, not old predictions, own the replayed prefix."""
import pytest

from suites.frontend.bpu.bpu.case.common_recovery import check_common_recovery
from suites.frontend.bpu.bpu.coverage.common_recovery import CommonRecoveryCoverage
from suites.frontend.bpu.bpu.model.common_recovery import PROFILES


@pytest.mark.feature('BPU-INT-043')
@pytest.mark.parametrize('profile', PROFILES, ids=lambda profile: profile.name)
async def test_actual_recovery_classification_replays_only_executed_conditional_results(
        bpu_agent, bpu_sc_output, profile):
    coverage = CommonRecoveryCoverage(profile)
    try:
        await check_common_recovery(bpu_agent, profile, coverage)
    finally:
        coverage.write(bpu_sc_output)
