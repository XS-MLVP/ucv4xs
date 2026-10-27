"""092: representative short/long history classes, not a physical matrix."""
import pytest
from bpuverify.bpu.case.indirect_service import check_indirect_service
from bpuverify.bpu.coverage.indirect_service import IndirectServiceCoverage


@pytest.mark.feature('BPU-INT-092')
@pytest.mark.parametrize('table',(0,2),ids=('short-history','long-history'))
async def test_original_indirect_targets_defer_four_context_effects_until_actual_service_and_new_consumers(bpu_agent,bpu_sc_output,table):
    coverage=IndirectServiceCoverage(table)
    try:await check_indirect_service(bpu_agent,coverage,table)
    finally:coverage.write(bpu_sc_output)
