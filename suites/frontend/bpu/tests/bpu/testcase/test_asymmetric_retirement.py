"""Compare logical owner results; same-cycle lane outputs are not paired origins."""
import pytest

from suites.frontend.bpu.bpu.case.asymmetric_retirement import check_asymmetric_retirement
from suites.frontend.bpu.bpu.coverage.asymmetric_retirement import AsymmetricRetirementCoverage


@pytest.mark.feature('BPU-INT-086')
async def test_two_histories_service_in_different_logical_orders_on_independent_owners(bpu_agent, bpu_sc_output):
    coverage = AsymmetricRetirementCoverage()
    try:
        await check_asymmetric_retirement(bpu_agent, coverage)
    finally:
        coverage.write(bpu_sc_output)
