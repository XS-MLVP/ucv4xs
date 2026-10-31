"""Short-window aliases must not merge independent long-window providers."""

import pytest

from suites.frontend.bpu.utage.coverage.catalog import utage_long_history_coverage_model
from suites.frontend.bpu.utage.coverage.catalog import write_utage_long_history_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.utage.case.long_history_scenario import check_short_alias_long_history


@pytest.mark.feature("BPU-UTAGE-018")
async def test_short_aliases_keep_long_history_providers_and_lower_fallback(utage_agent):
    coverage = utage_long_history_coverage_model()
    await check_short_alias_long_history(utage_agent, coverage)
    coverage.assert_coverage(100.0)
    write_utage_long_history_coverage(coverage, REPO_ROOT)
