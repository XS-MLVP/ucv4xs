"""Full same-PC way profiles stay independent across the high hash grid."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_high_hash_full_way_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_high_hash_full_way_coverage
from bpuverify.abtb.case.high_hash_scenario import HighHashFullWayGrid
from bpuverify.abtb.case.high_hash_scenario import ROUTES
from bpuverify.abtb.case.high_hash_scenario import route_name
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-047")
async def test_high_hash_grid_keeps_full_way_profiles_isolated(abtb_agent):
    coverage = abtb_high_hash_full_way_coverage_model()
    state = await HighHashFullWayGrid.prepare(abtb_agent)
    for route in ROUTES:
        await state.age_route(route)
        for vector in state.vectors[route]:
            way = await state.recover_position(route, vector)
            coverage.sample({
                "route_way": f"{route_name(route)}_way_{way}"
            })

    coverage.assert_coverage(100.0)
    write_abtb_high_hash_full_way_coverage(coverage, REPO_ROOT)
