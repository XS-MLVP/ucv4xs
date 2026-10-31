"""Explicit cross-region target-feedback diagnostic, without feature credit."""
from suites.frontend.bpu.bpu.case.ittage_region import check_region_feedback
from suites.frontend.bpu.runtime.paths import REPO_ROOT


async def test_cross_region_confidence_and_target_updates(bpu_agent, bpu_sc_output):
    await check_region_feedback(bpu_agent, REPO_ROOT, bpu_sc_output)
