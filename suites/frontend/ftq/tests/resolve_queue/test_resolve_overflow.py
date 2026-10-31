"""ResolveQueue branch-slot capacity: excess resolves must not corrupt state.

The FTQ entry stores `ResolveEntryBranchNumber = 8` branch reports, while the
DefaultConfig BPU meta can describe `NumBtbResultEntries = 10` positions.  A
fetch block can therefore legally produce a ninth branch resolve for one FTQ
entry.  The safe contract is to keep the first eight recorded reports and drop
the excess; the current RTL instead indexes the branch Vec out of range, which
wraps and overwrites an existing report.
"""

from __future__ import annotations

import pytest

from tests.resolve_queue.support import report

pytestmark = pytest.mark.feature("FTQ-RQ-011")


def _branches(agent):
    training = agent.training()
    return [] if training is None else [
        (branch.position, branch.target) for branch in training.branches]


@pytest.mark.rtl_defect
@pytest.mark.xfail(
    strict=True,
    reason="ninth branch resolve overwrites slot 7 instead of being dropped",
)
async def test_ninth_branch_resolve_is_dropped_not_overwritten(resolve_queue_agent):
    agent = resolve_queue_agent
    for offset in range(1, 9):
        await agent.resolve([report(0, offset=offset,
                                    target=0x9000_0000 + offset * 0x100,
                                    mispredict=0)])
    assert _branches(agent) == [
        (offset, 0x9000_0000 + offset * 0x100) for offset in range(1, 9)]

    await agent.resolve([report(0, offset=9, target=0xA000_0000,
                                mispredict=0)])

    # The eight accepted reports must be preserved; the excess must not
    # replace one of them.
    assert _branches(agent) == [
        (offset, 0x9000_0000 + offset * 0x100) for offset in range(1, 9)]


@pytest.mark.rtl_defect
@pytest.mark.xfail(
    strict=True,
    reason="same-cycle group larger than free slots wraps to slot 0",
)
async def test_same_cycle_group_overflow_preserves_existing_branch(resolve_queue_agent):
    agent = resolve_queue_agent
    for offset in range(1, 7):
        await agent.resolve([report(0, offset=offset,
                                    target=0x9000_0000 + offset * 0x100,
                                    mispredict=0)])
    assert _branches(agent) == [
        (offset, 0x9000_0000 + offset * 0x100) for offset in range(1, 7)]

    await agent.resolve([
        report(0, offset=7, target=0x9000_0700, mispredict=0),
        report(0, offset=8, target=0x9000_0800, mispredict=0),
        report(0, offset=9, target=0xA000_0000, mispredict=0),
    ])

    # Slots 0..5 are already valid; the two reports that fit go to slots 6..7
    # and the third must be dropped.  Slot 0 must still hold report 1.
    assert _branches(agent) == [
        (offset, 0x9000_0000 + offset * 0x100) for offset in range(1, 9)]
