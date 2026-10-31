"""066: T provider wins over NT base and its original source learns useful."""
import pytest
from suites.frontend.bpu.bpu.case.early_positive import check_early_positive
from suites.frontend.bpu.bpu.coverage.early_positive import EarlyPositiveCoverage


@pytest.mark.feature('BPU-INT-066')
async def test_owned_positive_provider_overrules_negative_ahead_and_learns_from_original_source(bpu_agent,bpu_sc_output):
    coverage=EarlyPositiveCoverage()
    try:await check_early_positive(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
