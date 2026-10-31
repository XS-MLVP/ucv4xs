"""Every resolve slot must retain its branch/prediction-state association."""
import pytest

from suites.frontend.bpu.tage.coverage.catalog import tage_resolve_slot_coverage_model
from suites.frontend.bpu.tage.coverage.catalog import write_tage_resolve_slot_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.case.resolve_slot_scenario import check_provider_matrix
from suites.frontend.bpu.tage.case.resolve_slot_scenario import check_qualification_matrix


@pytest.mark.feature('BPU-TAGE-027')
async def test_every_resolve_slot_trains_all_provider_depths_and_preserves_residents(tage_agent):
    coverage = tage_resolve_slot_coverage_model('provider')
    await check_provider_matrix(tage_agent, coverage)
    coverage.assert_coverage(100)
    write_tage_resolve_slot_coverage(coverage, REPO_ROOT, 'provider')


@pytest.mark.feature('BPU-TAGE-028')
async def test_sparse_resolve_qualification_and_metadata_association(tage_agent):
    coverage = tage_resolve_slot_coverage_model('qualification')
    await check_qualification_matrix(tage_agent, coverage)
    coverage.assert_coverage(100)
    write_tage_resolve_slot_coverage(coverage, REPO_ROOT, 'qualification')
