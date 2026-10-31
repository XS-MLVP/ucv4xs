"""Longest T provider protection is not covered by the short-table program."""
import pytest

from suites.frontend.bpu.bpu.case.early_long_positive_protection import check_early_long_positive_protection
from suites.frontend.bpu.bpu.coverage.early_long_positive_protection import EarlyLongPositiveProtectionCoverage
from suites.frontend.bpu.bpu.model.early_long_positive_protection import EDGES


@pytest.mark.feature('BPU-INT-066')
@pytest.mark.parametrize('mode', tuple(EDGES))
async def test_longest_taken_record_limits_without_backward_allocation(bpu_agent, bpu_sc_output, mode):
    coverage = EarlyLongPositiveProtectionCoverage()
    try:
        await check_early_long_positive_protection(bpu_agent, mode, coverage)
    finally:
        coverage.write(bpu_sc_output)
