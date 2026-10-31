"""Physical used-feedback matrix under genuine forward/backward CommonHR."""
import pytest
from suites.frontend.bpu.bpu.case.sc.used_nonzero_checks import run_used_case

# Measured on the 2026-10-21 full BPU program run; scheduling hint only.
pytestmark = pytest.mark.estimated_runtime(76)

@pytest.mark.feature('BPU-INT-061')
@pytest.mark.parametrize('bank', (0, 1), ids=('bank0', 'bank1'))
@pytest.mark.parametrize('way', range(4), ids=lambda value: f'way{value}')
@pytest.mark.parametrize('profile', ('agree', 'disagree'))
@pytest.mark.parametrize('direction', ('forward', 'backward'))
async def test_sc_used_nonzero_history(bpu_agent, bpu_sc_output, bank, way, profile, direction):
    await run_used_case(bpu_agent, bpu_sc_output, bank=bank, way=way, profile=profile, direction=direction)
