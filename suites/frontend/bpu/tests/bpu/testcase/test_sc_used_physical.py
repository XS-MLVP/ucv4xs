"""All two banks/four ways/both agreement profiles use real DUT feedback."""
import pytest
from suites.frontend.bpu.bpu.case.sc.used_checks import run_used_case

# Measured on the 2026-10-21 full BPU program run; scheduling hint only.
pytestmark = pytest.mark.estimated_runtime(35)

@pytest.mark.feature('BPU-INT-060')
@pytest.mark.parametrize('bank', (0, 1), ids=('bank0', 'bank1'))
@pytest.mark.parametrize('way', range(4), ids=lambda value: f'way{value}')
@pytest.mark.parametrize('profile', ('agree', 'disagree'))
async def test_physical_sc_used_matrix(bpu_agent, bpu_sc_output, bank, way, profile):
    await run_used_case(bpu_agent, bpu_sc_output, bank=bank, way=way, profile=profile)
