"""A real NT recovery may not pre-count an unexecuted later conditional."""
import pytest
from bpuverify.bpu.case.common_history import check_common_history
from bpuverify.bpu.coverage.common_history import CommonHistoryCoverage


@pytest.mark.parametrize('public_only',(False,True),ids=('committed-state','public-consumer'))
@pytest.mark.parametrize('later_conditional',(
    pytest.param(False,id='later-direct-control',marks=pytest.mark.feature('BPU-INT-043')),
    pytest.param(True,id='later-conditional',marks=pytest.mark.feature('BPU-INT-094'))))
async def test_original_not_taken_recovery_replays_only_executed_conditional_prefix(bpu_agent,bpu_sc_output,later_conditional,public_only):
    coverage=CommonHistoryCoverage(later_conditional=later_conditional,public_only=public_only)
    try:await check_common_history(bpu_agent,coverage,later_conditional=later_conditional,public_only=public_only)
    finally:coverage.write(bpu_sc_output)
