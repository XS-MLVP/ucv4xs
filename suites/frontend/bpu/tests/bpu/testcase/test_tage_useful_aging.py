"""Real sources, not forced predictor state or a bank/set sweep."""
import pytest
from suites.frontend.bpu.bpu.case.tage.aging import check_aging


@pytest.mark.feature('BPU-INT-073')
@pytest.mark.feature('BPU-INT-072')
@pytest.mark.parametrize('trigger',('demand','correct-update'))
async def test_tage_qualified_failure_useful_reset_and_recovery(bpu_agent,bpu_sc_output,trigger):
    await check_aging(bpu_agent,bpu_sc_output,trigger)
