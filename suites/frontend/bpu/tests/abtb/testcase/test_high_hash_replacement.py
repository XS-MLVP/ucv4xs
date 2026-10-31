"""Replacement in one high-set hash route preserves all fifteen peers."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.coverage.catalog import abtb_high_hash_replacement_coverage_model
from suites.frontend.bpu.abtb.coverage.catalog import write_abtb_high_hash_replacement_coverage
from suites.frontend.bpu.abtb.case.high_hash_scenario import HighHashFullWayGrid
from suites.frontend.bpu.abtb.case.high_hash_scenario import ROUTES
from suites.frontend.bpu.abtb.case.high_hash_scenario import route_name
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-048")
async def test_high_hash_replacement_preserves_other_route_profiles(abtb_agent):
    coverage = abtb_high_hash_replacement_coverage_model()
    state = await HighHashFullWayGrid.prepare(abtb_agent)
    for route in ROUTES:
        await state.replace_route(route)
        coverage.sample({
            "route": route_name(route),
            "isolation": "peers_preserved",
        })

    coverage.assert_coverage(100.0)
    write_abtb_high_hash_replacement_coverage(coverage, REPO_ROOT)
