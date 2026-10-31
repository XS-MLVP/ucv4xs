"""Independent scenarios are pytest items, not a serial inner-loop matrix."""
import pytest

from suites.frontend.bpu.tage.coverage.dual import DUAL_MODES
from suites.frontend.bpu.tage.coverage.dual import tage_dual_shadow_coverage_model
from suites.frontend.bpu.tage.coverage.dual import write_tage_dual_shadow_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.case.dual_shadow_scenario import check_case


@pytest.mark.feature('BPU-TAGE-035')
@pytest.mark.parametrize('bank', range(4), ids=lambda bank: f'bank{bank}')
@pytest.mark.parametrize('depth', range(4), ids=lambda depth: f'depth{depth}')
@pytest.mark.parametrize('mode', DUAL_MODES)
async def test_dual_feedback_retains_independent_counters_across_companion_states(tage_agent, bank, depth, mode):
    coverage = tage_dual_shadow_coverage_model()
    await check_case(tage_agent, bank=bank, depth=depth, mode=mode)
    for phase in ('native', 'forward', 'reverse'):
        coverage.sample(dict(bank=bank, depth=depth, mode=mode, phase=phase))
    # Preserve the full 384-bin schema in each contribution. The complete
    # production run asserts 100% only after merging all 128 pytest items.
    write_tage_dual_shadow_coverage(coverage, REPO_ROOT)
