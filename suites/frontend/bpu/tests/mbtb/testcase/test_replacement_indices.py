"""One behavioral feature, not one functional ID per copied LRU cell."""
import pytest

from bpuverify.mbtb.coverage.catalog import mbtb_replacement_coverage_model
from bpuverify.mbtb.coverage.catalog import write_mbtb_replacement_coverage
from bpuverify.mbtb.case.replacement_scenario import TOUCH_MODES
from bpuverify.mbtb.case.replacement_scenario import check_case
from bpuverify.mbtb.coverage.semantic import SemanticCoverage, RULES
from bpuverify.common.env.paths import REPO_ROOT


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
    mbtb_agent.reference.raise_failure()
    semantic.record('checked', rule, index=index, align=align, upper=upper)
    assert coverage.cross_coverage('all_dimensions') == pytest.approx(100 / 1024)
    write_mbtb_replacement_coverage(coverage, REPO_ROOT, semantic_groups=semantic.groups.values())
