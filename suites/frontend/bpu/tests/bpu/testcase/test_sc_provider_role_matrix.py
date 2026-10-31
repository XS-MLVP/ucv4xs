"""Intent only: qualified four-key provider roles and shadow lifecycles."""
import pytest
from suites.frontend.bpu.bpu.case.sc.role import check_provider_roles
from suites.frontend.bpu.bpu.coverage.sc.role import cases as provider_role_cases
from suites.frontend.bpu.bpu.coverage.sc.role import matrix_coverage as provider_role_coverage
from suites.frontend.bpu.bpu.coverage.sc.role import physical_bias_coverage
from suites.frontend.bpu.bpu.case.sc.role_scenarios import identity as provider_role_identity

# Measured on the 2026-10-21 full BPU program run; scheduling hint only.
pytestmark = pytest.mark.estimated_runtime(34)

@pytest.mark.feature('BPU-INT-041')
@pytest.mark.parametrize('case', provider_role_cases(), ids=provider_role_identity)
async def test_four_key_provider_role_matrix(bpu_agent, bpu_sc_output, case):
    await check_provider_roles(bpu_agent, bpu_sc_output, case,
        (provider_role_coverage(), physical_bias_coverage()))
