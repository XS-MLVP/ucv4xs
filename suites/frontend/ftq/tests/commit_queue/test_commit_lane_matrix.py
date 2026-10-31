"""CommitQueue: deterministic lane-priority sweep over all 64 memory slots."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.oracle import CallRet

WIDTH = 8


def rows(lane: int, value: CallRet) -> tuple[CallRet | None, ...]:
    values = [None] * WIDTH
    values[lane] = value
    return tuple(values)


@pytest.mark.feature("FTQ-CQ-002")
async def test_every_memory_slot_accepts_each_lane_priority(commit_queue_agent):
    agent = commit_queue_agent
    # With depth zero, enqueue and dequeue indices walk together, so each
    # cycle writes a different physical slot.  Sweeping the sole valid lane
    # covers every (slot, lane-priority) assignment and proves FIFO ordering.
    for lane in range(WIDTH):
        for index in range(64):
            expected = CallRet(index, 1 + (lane % 3))
            assert await agent.submit(rows(lane, expected)) == expected
    for _ in range(2):
        await agent.submit((None,) * WIDTH)
    assert agent.training() is None
