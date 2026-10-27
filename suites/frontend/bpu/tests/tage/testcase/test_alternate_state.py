import pytest

from bpuverify.tage.coverage.catalog import tage_alternate_coverage_model
from bpuverify.tage.coverage.catalog import write_tage_alternate_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.tage.case.alternate_scenario import check_pair_matrix
from bpuverify.tage.case.alternate_scenario import check_mixed_overlap


@pytest.mark.feature('BPU-TAGE-029')
async def test_exact_alternate_provider_state_in_every_prediction_slot(tage_agent):
    coverage = tage_alternate_coverage_model('pair')
    await check_pair_matrix(tage_agent, coverage)
    coverage.assert_coverage(100)
    write_tage_alternate_coverage(coverage, REPO_ROOT, 'pair')


@pytest.mark.feature('BPU-TAGE-030')
async def test_mixed_resident_and_alternate_slots_preserve_overlapped_association(tage_agent):
    coverage = tage_alternate_coverage_model('mixed')
    await check_mixed_overlap(tage_agent, coverage)
    coverage.assert_coverage(100)
    write_tage_alternate_coverage(coverage, REPO_ROOT, 'mixed')
