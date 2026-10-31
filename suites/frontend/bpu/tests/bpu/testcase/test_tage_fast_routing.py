import pytest

from suites.frontend.bpu.bpu.case.tage.fast_routing import check_fast_routing
from suites.frontend.bpu.bpu.coverage.tage.fast_routing import RoutingCoverage,DISCOVERIES
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature('BPU-INT-078')
@pytest.mark.parametrize('discovery',DISCOVERIES)
async def test_opposed_owned_directions_distinguish_raw_fast_and_qualified_final_provider(bpu_agent,discovery):
    coverage = RoutingCoverage(discovery)
    try:
        await check_fast_routing(bpu_agent,coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'bpu'))
