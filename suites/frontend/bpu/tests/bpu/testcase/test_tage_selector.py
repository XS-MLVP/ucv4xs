"""Real TAGE selector training, saturation, isolation and public consumption."""
import pytest
from suites.frontend.bpu.bpu.case.tage.selector import check_selector


@pytest.mark.feature('BPU-INT-072')
async def test_tage_selector_qualified_updates_and_fresh_consumers(bpu_agent,bpu_sc_output):
    await check_selector(bpu_agent,bpu_sc_output)
