"""MSHR pool capacity, duplicate suppression and acquire arbitration."""

from __future__ import annotations

import pytest


@pytest.mark.feature("ICACHE-MISSUNIT-001")
async def test_fetch_and_prefetch_pools_are_separate(missunit_agent):
    agent = missunit_agent
    for index in range(agent.model.fetch_mshrs):
        await agent.submit_fetch(0x1000 + index * 0x40, 0x10 + index)
    assert agent.fetch_ready() == 0, "the fetch pool must be full"
    assert agent.prefetch_ready() == 1, "prefetch capacity must be untouched"
    assert agent.model.fetch_ready() == 0
    assert agent.model.prefetch_ready() == 1
    for index in range(agent.model.prefetch_mshrs):
        await agent.submit_prefetch(0x8000 + index * 0x40, 0x20 + index)
    assert agent.prefetch_ready() == 0
    assert sorted(agent.occupied()) == list(
        range(agent.model.fetch_mshrs + agent.model.prefetch_mshrs))


@pytest.mark.feature("ICACHE-MISSUNIT-002")
async def test_duplicate_request_does_not_allocate(missunit_agent):
    agent = missunit_agent
    await agent.submit_fetch(0x2000, 0x30)
    # Same block and set: accepted (ready) but it must not take a second MSHR.
    await agent.submit_fetch(0x2000, 0x30)
    assert agent.occupied() == [0], "a duplicate must reuse the live MSHR"
    # The same block in another set is a different miss (VIPT aliasing).
    await agent.submit_fetch(0x2000, 0x31)
    assert agent.occupied() == [0, 1]


@pytest.mark.feature("ICACHE-MISSUNIT-002")
async def test_duplicate_accept_still_needs_a_free_pool(missunit_agent):
    """A duplicate must be accepted even when every fetch MSHR is taken."""
    agent = missunit_agent
    for index in range(agent.model.fetch_mshrs):
        await agent.submit_fetch(0x2800 + index * 0x40, 0x38 + index)
    assert agent.fetch_ready() == 0
    before = agent.occupied()
    # submit_fetch() itself fails unless the DUT asserted ready on the sampling
    # edge, so reaching this point proves the hit path acknowledged it.
    await agent.submit_fetch(0x2800, 0x38)
    assert agent.occupied() == before


@pytest.mark.feature("ICACHE-MISSUNIT-002")
async def test_prefetch_matching_the_same_cycle_fetch_is_a_duplicate(missunit_agent):
    agent = missunit_agent
    fetch_ok, prefetch_ok = await agent.submit_same_cycle(
        0x3000, 0x40, 0x3000, 0x40)
    assert fetch_ok == 1 and prefetch_ok == 1
    occupied = agent.occupied()
    assert len(occupied) == 1, f"the prefetch must not allocate a second entry: {occupied}"
    assert occupied[0] < agent.model.fetch_mshrs, "the fetch must own the entry"


@pytest.mark.feature("ICACHE-MISSUNIT-003")
async def test_fetch_wins_the_memory_channel(missunit_agent):
    agent = missunit_agent
    # The prefetch is allocated first, so arrival order alone would favour it.
    await agent.submit_prefetch(0x4000, 0x50)
    await agent.submit_fetch(0x4100, 0x51)
    issues = await agent.drain()
    sources = [issue.source for issue in issues]
    assert sources == [0, agent.model.fetch_mshrs], (
        f"fetch must own the channel first, got sources {sources}")


@pytest.mark.feature("ICACHE-MISSUNIT-003")
async def test_fetch_priority_survives_a_previous_prefetch_grant(missunit_agent):
    """Priority must not depend on which pool issued last."""
    agent = missunit_agent
    await agent.submit_prefetch(0x4200, 0x52)
    first = await agent.drain()
    assert [issue.source for issue in first] == [agent.model.fetch_mshrs]
    await agent.complete(first[0])
    await agent.submit_prefetch(0x4300, 0x53)
    await agent.submit_fetch(0x4400, 0x54)
    issues = await agent.drain()
    assert [issue.source for issue in issues] == [0, agent.model.fetch_mshrs], (
        "a fetch must still win after a prefetch grant")


@pytest.mark.feature("ICACHE-MISSUNIT-004")
async def test_prefetch_serves_in_arrival_order(missunit_agent):
    agent = missunit_agent
    blocks = [0x5000 + index * 0x40 for index in range(4)]
    for index, block in enumerate(blocks):
        await agent.submit_prefetch(block, 0x60 + index)
    issues = await agent.drain()
    order = [issue.block for issue in issues]
    assert order == blocks, f"prefetch order {order} != arrival order {blocks}"
    assert [issue.source for issue in issues] == [
        agent.model.fetch_mshrs + index for index in range(4)]


@pytest.mark.feature("ICACHE-MISSUNIT-011")
async def test_every_mshr_slot_owns_and_completes_its_transaction(missunit_agent):
    """Fill both pools and service all fourteen slots through a full FIFO wrap."""
    agent = missunit_agent
    agent.replacer.way = 0b10
    for index in range(agent.model.fetch_mshrs):
        await agent.submit_fetch(0x9000 + index * 0x40, 0x90 + index)
    for index in range(agent.model.prefetch_mshrs):
        await agent.submit_prefetch(0xA000 + index * 0x40, 0xA0 + index)
    assert len(agent.occupied()) == agent.model.fetch_mshrs + agent.model.prefetch_mshrs

    issues = await agent.drain()
    expected_sources = list(range(agent.model.fetch_mshrs + agent.model.prefetch_mshrs))
    assert [issue.source for issue in issues] == expected_sources, (
        "fetch slots issue first (lowest index), then prefetch slots in FIFO order")

    # Serve the refills in reverse order: the slots are independent, so any
    # completion order must preserve each entry's own block/set/way.
    seen = set()
    for issue in reversed(issues):
        response = await agent.complete(issue)
        assert response.valid == 1
        assert response.block == issue.block and response.vset == issue.vset
        assert response.waymask == 1 << agent.replacer.way
        assert response.meta_write == 1 and response.data_write == 1
        seen.add(issue.source)
    assert seen == set(expected_sources)
    assert agent.occupied() == []
    assert agent.wfi_safe() == 1
