"""Real writes, not saturated holds, establish simultaneous hit/allocation."""
import pytest

from suites.frontend.bpu.tage.coverage.catalog import tage_mixed_writes_coverage_model
from suites.frontend.bpu.tage.coverage.catalog import write_tage_mixed_writes_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.case.definitions import SAME_BANK_PCS
from suites.frontend.bpu.tage.case.mixed_writes_scenario import check_case


@pytest.mark.feature('BPU-TAGE-031')
async def test_counter_update_and_cold_allocation_write_both_ways_in_one_event(tage_agent):
    coverage = tage_mixed_writes_coverage_model('update')
    for context, pc in enumerate(SAME_BANK_PCS):
        for way in range(2):
            pair = None
            for counter in (1, 2):
                pair = await check_case(tage_agent, coverage, pc, context, way, counter, pair=pair)
    coverage.assert_coverage(100.0)
    write_tage_mixed_writes_coverage(coverage, REPO_ROOT, 'update')


@pytest.mark.feature('BPU-TAGE-032')
async def test_noop_and_ineligible_provider_do_not_create_a_second_write(tage_agent):
    coverage = tage_mixed_writes_coverage_model('gated')
    for context, pc in enumerate(SAME_BANK_PCS):
        for way in range(2):
            pair = None
            for reason in ('saturated', 'mbtb_miss', 'inactive', 'disabled'):
                pair = await check_case(tage_agent, coverage, pc, context, way,
                                        0 if reason == 'saturated' else 1, reason=reason, pair=pair)
    coverage.assert_coverage(100.0)
    write_tage_mixed_writes_coverage(coverage, REPO_ROOT, 'gated')
