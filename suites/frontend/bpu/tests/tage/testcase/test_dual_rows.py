"""Two TAGE write ports must retain independent pending rows and useful updates."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.tage.coverage.catalog import tage_dual_rows_coverage_model
from suites.frontend.bpu.tage.coverage.catalog import write_tage_dual_rows_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.case.dual_rows_scenario import check_dual_feedback_mode


@pytest.mark.feature("BPU-TAGE-024")
async def test_dual_way_pending_rows_keep_counters_useful_and_neighbors(tage_agent):
    coverage = tage_dual_rows_coverage_model()
    adjacent_rows, adjacent = await check_dual_feedback_mode(tage_agent, coverage, adjacent=True)
    serial_rows, serial = await check_dual_feedback_mode(tage_agent, coverage, adjacent=False)
    assert serial_rows == adjacent_rows
    for serial_stage, adjacent_stage in zip(serial, adjacent, strict=True):
        for serial_prediction, adjacent_prediction in zip(serial_stage, adjacent_stage, strict=True):
            assert serial_prediction.valids[:2] == adjacent_prediction.valids[:2]
            assert serial_prediction.takens[:2] == adjacent_prediction.takens[:2]
            for serial_meta, adjacent_meta in zip(serial_prediction.metas[:2], adjacent_prediction.metas[:2], strict=True):
                assert serial_meta["providerTakenCtr_value"] == adjacent_meta["providerTakenCtr_value"]
                assert serial_meta["providerUsefulCtr_value"] >= adjacent_meta["providerUsefulCtr_value"]
    coverage.assert_coverage(100.0)
    write_tage_dual_rows_coverage(coverage, REPO_ROOT)
