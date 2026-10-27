"""Global useful aging must select the correct table without losing neighbors."""

from __future__ import annotations

import pytest

from bpuverify.utage.coverage.catalog import utage_aging_matrix_coverage_model
from bpuverify.utage.coverage.catalog import write_utage_aging_matrix_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.case.aging_scenario import check_two_round_aging


@pytest.mark.feature("BPU-UTAGE-017")
async def test_two_aging_rounds_distinguish_decrement_from_shift_in_every_bank(utage_agent):
    coverage = utage_aging_matrix_coverage_model()
    await check_two_round_aging(utage_agent, coverage)
    coverage.assert_coverage(100.0)
    write_utage_aging_matrix_coverage(coverage, REPO_ROOT)
