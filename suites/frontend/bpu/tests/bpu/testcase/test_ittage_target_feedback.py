"""Integrated feedback lifecycle intent; no pins, edges or cycle sleeps."""
import pytest
from suites.frontend.bpu.bpu.case.ittage_feedback import check_target_feedback
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature('BPU-INT-062')
async def test_provider_alternate_confidence_and_target_updates(bpu_agent):
    await check_target_feedback(bpu_agent, REPO_ROOT)
