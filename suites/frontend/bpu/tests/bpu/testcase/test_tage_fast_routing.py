import pytest

from bpuverify.bpu.case.tage.fast_routing import check_fast_routing
from bpuverify.bpu.coverage.tage.fast_routing import RoutingCoverage,DISCOVERIES
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature('BPU-INT-078')
@pytest.mark.parametrize('discovery',DISCOVERIES)
async def test_opposed_owned_directions_distinguish_raw_fast_and_qualified_final_provider(bpu_agent,discovery):
    coverage = RoutingCoverage(discovery)
    try:
        await check_fast_routing(bpu_agent,coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'bpu'))
