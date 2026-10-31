"""Adjacent fetch starts share one MainBTB window with remapped positions."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.mbtb.coverage.catalog import mbtb_overlapping_windows_coverage_model
from suites.frontend.bpu.mbtb.coverage.catalog import write_mbtb_overlapping_windows_coverage
from suites.frontend.bpu.mbtb.checker.assertions import assert_miss
from suites.frontend.bpu.mbtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.mbtb.checker.assertions import matching_way
from suites.frontend.bpu.mbtb.checker.assertions import train
from suites.frontend.bpu.mbtb.case.definitions import BranchVector
from suites.frontend.bpu.mbtb.case.definitions import DIRECT
from suites.frontend.bpu.mbtb.case.definitions import NUM_WAYS
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-MBTB-018")
async def test_neighboring_fetch_starts_remap_the_shared_window(mbtb_agent):
    coverage = mbtb_overlapping_windows_coverage_model()
    await mbtb_agent.reset()
    next_start = BranchVector(
        DIRECT.pc + 16, DIRECT.target + 0x400, DIRECT.position, DIRECT.branch_type
    )
    next_in_first_window = BranchVector(
        DIRECT.pc, next_start.target, DIRECT.position + 16, DIRECT.branch_type
    )

    for vector in (DIRECT, next_start):
        cold = await mbtb_agent.predict(vector.pc)
        assert_miss(cold)
        await train(mbtb_agent, vector, cold.meta_entries)

    first_window = await mbtb_agent.predict(DIRECT.pc)
    assert_vector_hit(first_window, DIRECT)
    assert_vector_hit(first_window, next_in_first_window)
    assert sum(entry.valid for entry in first_window.entries) == 2
    assert matching_way(first_window, DIRECT) // (NUM_WAYS + 1) != (
        matching_way(first_window, next_in_first_window) // (NUM_WAYS + 1)
    )
    coverage.sample({"phase": "overlapping_first_window"})

    second_window = await mbtb_agent.predict(next_start.pc)
    assert_vector_hit(second_window, next_start)
    assert sum(entry.valid for entry in second_window.entries) == 1
    assert all(
        not entry.valid or entry.target != DIRECT.target
        for entry in second_window.entries
    ), second_window
    coverage.sample({"phase": "shifted_second_window"})

    restored = await mbtb_agent.predict(DIRECT.pc)
    assert_vector_hit(restored, DIRECT)
    assert_vector_hit(restored, next_in_first_window)
    assert sum(entry.valid for entry in restored.entries) == 2
    coverage.sample({"phase": "first_window_retained"})
    coverage.assert_coverage(100.0)
    write_mbtb_overlapping_windows_coverage(coverage, REPO_ROOT)
