"""An aged full set can replace one way without disturbing either neighbor."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_flanked_replacement_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_flanked_replacement_coverage
from suites.frontend.bpu.abtb.case.flanked_scenario import AgedFlankedSet
from suites.frontend.bpu.abtb.case.flanked_scenario import BANKS
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-044")
async def test_aged_replacement_preserves_both_flanks_and_other_banks(abtb_agent):
    coverage = abtb_flanked_replacement_coverage_model()
    state = await AgedFlankedSet.prepare(abtb_agent)
    for bank in BANKS:
        await state.replace_bank(bank)
        coverage.sample({"replaced_bank": bank, "isolation": "both_flanks_and_peers"})

    coverage.assert_coverage(100.0)
    write_abtb_flanked_replacement_coverage(coverage, REPO_ROOT)
