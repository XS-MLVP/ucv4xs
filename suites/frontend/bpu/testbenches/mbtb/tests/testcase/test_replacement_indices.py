"""One behavioral feature, not one functional ID per copied LRU cell."""
import pytest

from suites.frontend.bpu.testbenches.mbtb.coverage.catalog import mbtb_replacement_coverage_model
from suites.frontend.bpu.testbenches.mbtb.coverage.catalog import write_mbtb_replacement_coverage
from suites.frontend.bpu.testbenches.mbtb.tests.scenarios.replacement_scenario import TOUCH_MODES
from suites.frontend.bpu.testbenches.mbtb.tests.scenarios.replacement_scenario import check_case
from suites.frontend.bpu.testbenches.mbtb.coverage.semantic import SemanticCoverage
from suites.frontend.bpu.testbenches.mbtb.coverage.semantic import RULES
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT


@pytest.mark.feature('BPU-MBTB-024')
@pytest.mark.mbtb_replacement_matrix
@pytest.mark.parametrize('align', range(2))
@pytest.mark.parametrize('upper', range(2))
@pytest.mark.parametrize('mode', TOUCH_MODES)
async def test_indexed_replacement_shares_alias_state_and_preserves_independent_neighbors(mbtb_agent, index, align, upper, mode):
    coverage = mbtb_replacement_coverage_model()
    semantic = SemanticCoverage('replacement')
    rule = dict(zip(TOUCH_MODES, RULES['replacement'], strict=True))[mode]

    class Checkpoint:
        def sample(self, value):
            coverage.sample(value)
            if value['phase'] == 'qualified':
                semantic.record('reached', rule, index=index, align=align, upper=upper)

    await check_case(mbtb_agent, Checkpoint(), index, align, upper, mode)
    mbtb_agent.check_learning()
    semantic.record('checked', rule, index=index, align=align, upper=upper)
    assert coverage.cross_coverage('all_dimensions') == pytest.approx(100 / 4096)
    write_mbtb_replacement_coverage(coverage, REPO_ROOT, semantic_groups=semantic.groups.values())
