"""MainBTB attribute changes overwrite a hit instead of allocating a way."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.mbtb.coverage.catalog import mbtb_attribute_rewrite_coverage_model
from suites.frontend.bpu.mbtb.coverage.catalog import write_mbtb_attribute_rewrite_coverage
from suites.frontend.bpu.mbtb.checker.assertions import assert_miss
from suites.frontend.bpu.mbtb.checker.assertions import assert_resident_pair
from suites.frontend.bpu.mbtb.checker.assertions import matching_way
from suites.frontend.bpu.mbtb.checker.assertions import train
from suites.frontend.bpu.mbtb.case.definitions import BranchVector
from suites.frontend.bpu.mbtb.case.definitions import CONDITIONAL
from suites.frontend.bpu.mbtb.case.definitions import NUM_WAYS
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-MBTB-014")
async def test_attribute_rewrite_reuses_hit_way_and_resets_counter(mbtb_agent):
    coverage = mbtb_attribute_rewrite_coverage_model()
    await mbtb_agent.reset()
    neighbor = BranchVector(CONDITIONAL.pc, CONDITIONAL.target + 0x400, 2, 2)
    cold = await mbtb_agent.predict(CONDITIONAL.pc)
    assert_miss(cold)
    await train(mbtb_agent, CONDITIONAL, cold.meta_entries)
    one = await mbtb_agent.predict(CONDITIONAL.pc)
    await train(mbtb_agent, neighbor, one.meta_entries)
    current = await mbtb_agent.predict(CONDITIONAL.pc)
    assert sum(entry.valid for entry in current.entries) == 2
    ways = (matching_way(current, CONDITIONAL), matching_way(current, neighbor))
    assert ways[0] != ways[1]
    assert ways[0] // NUM_WAYS == ways[1] // NUM_WAYS
    assert_resident_pair(current, CONDITIONAL, neighbor, ways, 2)

    for _ in range(3):
        await train(mbtb_agent, CONDITIONAL, current.meta_entries, taken=0)
        current = await mbtb_agent.predict(CONDITIONAL.pc)
    assert_resident_pair(current, CONDITIONAL, neighbor, ways, 0)
    coverage.sample({"phase": "aged_zero"})

    transitions = (
        ("conditional_to_direct", BranchVector(CONDITIONAL.pc, 0x4000_1800, 1, 2)),
        ("direct_to_indirect", BranchVector(CONDITIONAL.pc, 0x4000_2800, 1, 3)),
        ("indirect_to_conditional", BranchVector(CONDITIONAL.pc, 0x4000_3800, 1, 1)),
    )
    for label, rewritten in transitions:
        previous = next(
            entry
            for entry in current.entries
            if entry.valid and entry.position == rewritten.position
        )
        await train(mbtb_agent, rewritten, current.meta_entries)
        current = await mbtb_agent.predict(CONDITIONAL.pc)
        assert_resident_pair(current, rewritten, neighbor, ways, 2)
        assert previous.branch_type != rewritten.branch_type
        assert not any(
            entry.valid
            and entry.position == rewritten.position
            and entry.branch_type == previous.branch_type
            for entry in current.entries
        )
        coverage.sample({"phase": label})

    final = transitions[-1][1]
    await train(mbtb_agent, final, current.meta_entries, taken=0)
    after_training = await mbtb_agent.predict(CONDITIONAL.pc)
    assert_resident_pair(after_training, final, neighbor, ways, 1)
    coverage.sample({"phase": "trained_after_rewrite"})
    coverage.sample({"phase": "neighbor_preserved"})

    coverage.assert_coverage(100.0)
    write_mbtb_attribute_rewrite_coverage(coverage, REPO_ROOT)
