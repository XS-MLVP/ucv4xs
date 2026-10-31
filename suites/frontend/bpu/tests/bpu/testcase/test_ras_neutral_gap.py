"""Integrated strengthening of the existing omitted-notification contract."""
import pytest
from suites.frontend.bpu.bpu.case.ras.neutral_gap import check_neutral_gap
from suites.frontend.bpu.bpu.coverage.ras_neutral_gap import RasNeutralGapCoverage


@pytest.mark.feature('BPU-RAS-016')
async def test_genuine_neutral_retirement_reclaims_guarded_ras_credit_without_committing_stack_data(bpu_agent,bpu_sc_output):
    coverage=RasNeutralGapCoverage()
    try:await check_neutral_gap(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
