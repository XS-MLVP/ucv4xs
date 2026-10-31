"""Global useful aging must select the correct table without losing neighbors."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.utage.coverage.catalog import utage_aging_matrix_coverage_model
from suites.frontend.bpu.utage.coverage.catalog import write_utage_aging_matrix_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.utage.case.aging_scenario import check_two_round_aging


@pytest.mark.feature("BPU-UTAGE-017")
async def test_two_aging_rounds_distinguish_decrement_from_shift_in_every_bank(utage_agent):
    coverage = utage_aging_matrix_coverage_model()
    await check_two_round_aging(utage_agent, coverage)
    coverage.assert_coverage(100.0)
    write_utage_aging_matrix_coverage(coverage, REPO_ROOT)
