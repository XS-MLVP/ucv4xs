"""Mixed writes must forward resident counters, including saturated holds."""
import pytest

from suites.frontend.bpu.testbenches.tage.coverage.catalog import tage_overlap_coverage_model
from suites.frontend.bpu.testbenches.tage.coverage.catalog import write_tage_overlap_coverage
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT
from suites.frontend.bpu.testbenches.tage.model.vectors import SAME_BANK_PCS
from suites.frontend.bpu.testbenches.tage.tests.scenarios.overlapped_saturation_scenario import check_case


@pytest.mark.feature('BPU-TAGE-033')
async def test_adjacent_and_separated_mixed_feedback_forward_or_reread_counters(tage_agent):
    coverage = tage_overlap_coverage_model()
    for context, pc in enumerate(SAME_BANK_PCS):
        for way in range(2):
            pair = None
            for mode in ('adjacent', 'separated'):
                for counter in (1, 2):
                    pair = await check_case(tage_agent, coverage, pc, context, way, counter, mode, pair=pair)
    coverage.assert_coverage(100.0)
    write_tage_overlap_coverage(coverage, REPO_ROOT)
