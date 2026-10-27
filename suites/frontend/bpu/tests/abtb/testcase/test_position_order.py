"""Position-ordered counter updates for branches in one fetch block."""

from __future__ import annotations

import pytest

from bpuverify.abtb.coverage.catalog import abtb_position_order_coverage_model
from bpuverify.abtb.coverage.catalog import write_abtb_position_order_coverage
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import BranchVector
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-ABTB-013")
async def test_later_taken_branch_suppresses_earlier_conditional_only(abtb_agent):
    coverage = abtb_position_order_coverage_model()
    await abtb_agent.reset()
    early = BranchVector(0x4000_4800, 0x4000_5800, 2, 1)
    late = BranchVector(early.pc, 0x4000_5900, 9, 1)

    cold = await abtb_agent.predict(early.pc)
    assert_miss(cold)
    await train_taken(abtb_agent, early, cold.meta)
    first = await abtb_agent.predict(early.pc)
    early_way, early_entry = matching_entry(first, early.position, early.branch_type)
    assert early_entry.taken == 1
    assert early_entry.target == early.target

    await train_taken(abtb_agent, late, first.meta)
    paired = await abtb_agent.predict(early.pc)
    observed_early_way, suppressed = matching_entry(
        paired, early.position, early.branch_type
    )
    late_way, observed_late = matching_entry(
        paired, late.position, late.branch_type
    )
    assert observed_early_way == early_way
    assert late_way != early_way
    assert (suppressed.taken, suppressed.target) == (0, early.target)
    assert (observed_late.taken, observed_late.target) == (1, late.target)
    coverage.sample({"transition": "suppress"})

    # Training the earlier taken branch must not decrease the later branch.
    await train_taken(abtb_agent, early, paired.meta)
    recovered = await abtb_agent.predict(early.pc)
    _, restored = matching_entry(recovered, early.position, early.branch_type)
    _, surviving = matching_entry(recovered, late.position, late.branch_type)
    assert (restored.taken, restored.target) == (1, early.target)
    assert (surviving.taken, surviving.target) == (1, late.target)
    coverage.sample({"transition": "restore"})
    coverage.assert_coverage(100.0)
    write_abtb_position_order_coverage(coverage, REPO_ROOT)
