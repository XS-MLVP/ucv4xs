import pytest

from bpuverify.bpu.case.tage.alternate import check_alternate
from bpuverify.bpu.coverage.tage.alternate import AlternateCoverage
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature('BPU-INT-079')
async def test_shorter_history_alternate_beats_weak_provider_and_opposing_base_then_yields_to_strong_provider(bpu_agent):
    coverage = AlternateCoverage()
    try:
        await check_alternate(bpu_agent,coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'bpu'))
