"""Custom bounds of four global threshold registers, no bank/set matrix."""
import pytest
from suites.frontend.bpu.bpu.case.sc.bounds import check_bounds


@pytest.mark.feature('BPU-INT-070')
@pytest.mark.feature('BPU-INT-071')
@pytest.mark.parametrize('way',range(4))
@pytest.mark.parametrize('boundary',(
    pytest.param('lower',marks=pytest.mark.estimated_runtime(60)),
    pytest.param('upper',marks=pytest.mark.estimated_runtime(220)),
))
async def test_sc_custom_threshold_bounds(bpu_agent,bpu_sc_output,way,boundary):
    await check_bounds(bpu_agent,bpu_sc_output,way=way,boundary=boundary)
