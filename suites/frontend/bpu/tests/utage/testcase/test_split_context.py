"""Different index/tag ancestors are a semantic scenario, not a bank sweep."""
import pytest
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.utage.case.split_context import check_split_context_useful


@pytest.mark.feature('BPU-UTAGE-023')
async def test_high_index_low_tag_provider_useful_updates(utage_agent):
    await check_split_context_useful(utage_agent, REPO_ROOT / 'results/utage')
