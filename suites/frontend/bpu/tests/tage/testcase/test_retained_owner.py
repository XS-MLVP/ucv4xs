"""Each independently reset owner/depth scenario is a schedulable pytest item."""
import pytest

from bpuverify.tage.coverage.retained import tage_retained_owner_coverage_model
from bpuverify.tage.coverage.retained import write_tage_retained_owner_coverage
from bpuverify.common.env.paths import REPO_ROOT
from tests.tage.diagnostics.retained_owner_probe import check_case


@pytest.mark.feature('BPU-TAGE-034')
@pytest.mark.parametrize('bank', range(4), ids=lambda bank: f'bank{bank}')
@pytest.mark.parametrize('origin', range(2), ids=lambda origin: f'origin{origin}')
@pytest.mark.parametrize('depth', range(4), ids=lambda depth: f'depth{depth}')
@pytest.mark.parametrize('mode', ('pending', 'clean'))
async def test_captured_way_feedback_updates_retained_owner_at_every_depth(tage_agent, bank, origin, depth, mode):
    coverage = tage_retained_owner_coverage_model()
    await check_case(tage_agent, bank=bank, origin=origin, depth=depth, mode=mode)
    for phase in ('native', 'forward', 'reverse'):
        coverage.sample(dict(bank=bank, origin=origin, depth=depth, mode=mode, phase=phase))
    # Preserve the full 192-bin schema; production gates the merged matrix.
    write_tage_retained_owner_coverage(coverage, REPO_ROOT)
