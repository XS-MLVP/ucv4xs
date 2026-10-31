"""ResolveQueue: ownership, merge, filtering, flush, guard and reset."""

from __future__ import annotations

import pytest

from tests.resolve_queue.support import head
from tests.resolve_queue.support import positions
from tests.resolve_queue.support import report

pytestmark = pytest.mark.feature("FTQ-RQ-001")


async def test_new_index_creates_one_owned_entry_and_holds_under_backpressure(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(5, pc=0x8000_1000, offset=3,
                                target=0x8000_3000)])
    training = agent.training()
    assert training is not None
    assert (training.index, training.flag, training.start_pc) == (5, 0, 0x8000_1000)
    assert len(training.branches) == 1
    branch = training.branches[0]
    assert (branch.position, branch.target, branch.taken, branch.mispredict,
            branch.branch_type) == (3, 0x8000_3000, 1, 1, 1)
    # No ready consumer: the admitted entry is stable rather than silently lost.
    for _ in range(3):
        await agent.step(1)
        assert head(agent) == (5, 0, 0x8000_1000)


@pytest.mark.feature("FTQ-RQ-002")
async def test_same_index_lanes_merge_and_advance_enqueue_by_unique_entries(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([
        report(7, offset=2, target=0x8000_3100),
        report(7, offset=9, target=0x8000_3200),
        report(8, offset=4, target=0x8000_3300),
    ])
    training = agent.training()
    assert training.index == 7
    assert [(branch.position, branch.target) for branch in training.branches] == [
        (2, 0x8000_3100), (9, 0x8000_3200)]
    assert positions(agent) == [2, 9]

    drained = await agent.drain()
    assert (drained.index, positions(agent)) == (7, [4])


@pytest.mark.feature("FTQ-RQ-003")
async def test_later_resolve_updates_existing_index_without_duplicate(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(9, pc=0x8000_1000, offset=1)])
    assert head(agent) == (9, 0, 0x8000_1000)

    await agent.resolve([report(9, pc=0x8000_1000, offset=6)])
    training = agent.training()
    assert training.index == 9
    assert training.start_pc == 0x8000_1000
    assert positions(agent) == [1, 6]

    await agent.drain()
    await agent.step(2)
    assert agent.training() is None


@pytest.mark.feature("FTQ-RQ-004")
async def test_ifu_resolve_is_an_independent_always_accepted_source(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(4, offset=1, branch_type=3, ras_action=1,
                                mispredict=0)], source="ifu")
    training = agent.training()
    assert (training.index, training.flag) == (4, 0)
    branch = training.branches[0]
    assert (branch.branch_type, branch.ras_action) == (3, 1)


@pytest.mark.feature("FTQ-RQ-005")
async def test_backend_correct_direct_and_return_resolves_do_not_allocate(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(10, branch_type=2, mispredict=0, ras_action=0)])
    assert agent.training() is None
    await agent.resolve([report(11, branch_type=3, mispredict=1, ras_action=1)])
    assert agent.training() is None
    await agent.resolve([report(12, branch_type=1, mispredict=1, ras_action=0)])
    assert head(agent) == (12, 0, 0x8000_1000)


@pytest.mark.feature("FTQ-RQ-006")
async def test_ready_consumes_exactly_one_entry_and_empty_queue_stays_idle(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(5)])
    await agent.resolve([report(6)])
    assert head(agent) == (5, 0, 0x8000_1000)

    assert (await agent.drain()).index == 5
    assert head(agent) == (6, 0, 0x8000_1000)
    assert (await agent.drain()).index == 6
    await agent.step(2)
    assert agent.training() is None

    # Ready alone must not invent an entry.
    await agent.ready(True)
    await agent.step(2)
    assert agent.training() is None


@pytest.mark.feature("FTQ-RQ-007")
async def test_redirect_flushes_younger_entries_and_keeps_older_head(resolve_queue_agent):
    agent = resolve_queue_agent
    for index in (5, 6, 7):
        await agent.resolve([report(index, offset=index - 4)])
    assert head(agent) == (5, 0, 0x8000_1000)

    await agent.redirect(5)
    # Entry 5 is older than the redirect point and must survive.  Entries 6
    # and 7 were younger and must never be offered for predictor training.
    assert head(agent) == (5, 0, 0x8000_1000)
    await agent.drain()
    await agent.step(4)
    assert agent.training() is None


@pytest.mark.feature("FTQ-RQ-008")
async def test_bpu_enqueue_at_resident_index_invalidates_stale_speculation(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(5, offset=3)])
    assert positions(agent) == [3]

    await agent.bpu_enqueue(5)
    assert agent.training() is None

    await agent.resolve([report(5, offset=8)])
    assert positions(agent) == [8]

    # A different enqueue pointer is not an ownership collision.
    await agent.bpu_enqueue(6)
    assert head(agent) == (5, 0, 0x8000_1000)


@pytest.mark.feature("FTQ-RQ-009")
async def test_reserve_guard_stops_admission_but_preserves_drain(resolve_queue_agent):
    agent = resolve_queue_agent
    for index in range(12):
        await agent.resolve([report(index, offset=index % 16)])
    assert head(agent) == (0, 0, 0x8000_1000)

    # The 13th distinct entry is dropped while the guard is active.
    await agent.resolve([report(20, offset=15)])
    assert head(agent) == (0, 0, 0x8000_1000)

    for expected in range(12):
        drained = await agent.drain()
        assert drained.index == expected
    await agent.step(2)
    assert agent.training() is None


@pytest.mark.feature("FTQ-RQ-010")
async def test_reset_discards_pending_resolution_and_reinitializes(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(9)])
    assert agent.training() is not None

    await agent.reset()
    assert agent.training() is None

    await agent.resolve([report(2)])
    assert head(agent) == (2, 0, 0x8000_1000)
