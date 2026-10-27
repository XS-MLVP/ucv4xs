"""DefaultConfig eight-bit prediction tags must survive training and readback."""
import pytest

from bpuverify.utage.case.errors import UtageTagWidthMismatch
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.case.tag_width_scenario import check_guarded_pc_tag_width


@pytest.mark.feature('BPU-UTAGE-007')
async def test_utage_guarded_pc_tag_width(utage_agent):
    await check_guarded_pc_tag_width(utage_agent,
        REPO_ROOT / 'results/utage/tag-width-known-fail.json')
