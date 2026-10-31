"""CommitQueue: selective call/return retirement and bounded FIFO order."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.oracle import CallRet

WIDTH = 8
CAPACITY = 64
GUARD = 8


def rows(*entries: CallRet | None) -> tuple[CallRet | None, ...]:
    values = list(entries) + [None] * (WIDTH - len(entries))
    return tuple(values)


@pytest.mark.feature("FTQ-CQ-001")
async def test_only_call_and_return_actions_enter_the_queue(commit_queue_agent):
    agent = commit_queue_agent
    assert await agent.submit(rows(CallRet(3, 0), None, CallRet(4, 0))) is None
    assert await agent.submit(rows()) is None
    assert await agent.submit(rows(CallRet(5, 2))) == CallRet(5, 2)
    assert await agent.submit(rows()) is None


@pytest.mark.feature("FTQ-CQ-002")
async def test_lane_packing_preserves_program_order_and_payload(commit_queue_agent):
    agent = commit_queue_agent
    assert await agent.submit(rows(
        CallRet(10, 2), None, CallRet(11, 1), CallRet(12, 3),
        None, CallRet(13, 2))) == CallRet(10, 2)
    assert await agent.submit(rows()) == CallRet(11, 1)
    assert await agent.submit(rows()) == CallRet(12, 3)
    assert await agent.submit(rows()) == CallRet(13, 2)
    assert await agent.submit(rows()) is None


@pytest.mark.feature("FTQ-CQ-003")
async def test_simultaneous_enqueue_and_dequeue_preserve_fifo_without_bypass(commit_queue_agent):
    agent = commit_queue_agent
    stream = [
        rows(CallRet(20, 2)),
        rows(CallRet(21, 2), CallRet(22, 1)),
        rows(),
        rows(CallRet(23, 3)),
    ]
    observed = [await agent.submit(cycle) for cycle in stream]
    assert observed == [CallRet(20, 2), CallRet(21, 2), CallRet(22, 1), CallRet(23, 3)]
    assert await agent.submit(rows()) is None
    assert agent.checker.depth == 0


@pytest.mark.feature("FTQ-CQ-004")
async def test_capacity_guard_never_overwrites_queued_call_returns(commit_queue_agent):
    agent = commit_queue_agent
    for cycle_index in range(16):
        base = cycle_index * WIDTH
        cycle = tuple(
            CallRet((base + lane) % CAPACITY, 1 + (base + lane) % 3)
            if (base + lane) < 96 else None
            for lane in range(WIDTH)
        )
        await agent.submit(cycle)

    for _ in range(CAPACITY + 8):
        observed = await agent.submit(rows())
        if observed is None:
            break
    assert agent.checker.depth == 0


@pytest.mark.feature("FTQ-CQ-005")
async def test_reset_discards_all_pending_actions(commit_queue_agent):
    agent = commit_queue_agent
    await agent.submit(rows(CallRet(30, 2), CallRet(31, 1)))
    assert agent.training() == CallRet(30, 2)

    await agent.reset()
    assert agent.training() is None
    assert await agent.submit(rows(CallRet(32, 2))) == CallRet(32, 2)
