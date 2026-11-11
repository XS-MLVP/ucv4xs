"""DefaultConfig eight-bit prediction tags must survive training and readback."""
import pytest

from suites.frontend.bpu.testbenches.utage.tests.scenarios.errors import UtageTagWidthMismatch
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT
from suites.frontend.bpu.testbenches.utage.tests.scenarios.tag_width_scenario import check_guarded_pc_tag_width


@pytest.mark.feature('BPU-UTAGE-007')
async def test_utage_guarded_pc_tag_width(utage_agent):
    await check_guarded_pc_tag_width(utage_agent,
        REPO_ROOT / 'results/utage/tag-width-known-fail.json')
