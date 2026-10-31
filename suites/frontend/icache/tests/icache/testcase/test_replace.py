"""Replacement, fence.i and redirect flush at the whole-ICache level."""

from __future__ import annotations

import pytest

from suites.frontend.icache.icache.case.definitions import make_fetch
from suites.frontend.icache.icache.model import icache as model


def same_set_vaddr(set_index: int, tag_index: int) -> int:
    """An address in ``set_index`` with physical page tag ``tag_index``."""
    ptag = (tag_index << 2) | (set_index >> 6)
    return (ptag << 12) | ((set_index & 0x3F) << 6)


@pytest.mark.feature("ICACHE-ICACHE-006")
async def test_filling_a_set_evicts_the_plru_victim(icache_agent):
    agent = icache_agent
    set_index = 0x10
    addresses = [same_set_vaddr(set_index, tag) for tag in range(4)]
    expected_block = [addr >> 6 for addr in addresses]
    for address in addresses:
        observed = await agent.send(make_fetch(address, 15))
        assert observed.blocks[0].data == model.memory_data(address >> 6)

    # Touch the oldest block: the tree-PLRU must now consider it the newest.
    first = addresses[0]
    before = len(agent.acquires)
    await agent.send(make_fetch(first, 15))
    assert len(agent.acquires) == before, "the touched block must still be resident"

    # A fifth block in the same set evicts exactly one way.
    fifth = same_set_vaddr(set_index, 4)
    before = len(agent.acquires)
    await agent.send(make_fetch(fifth, 15))
    assert len(agent.acquires) == before + 1

    # The model knows which block was evicted; the DUT must agree.
    resident = [agent.model.hit_mask(block, set_index) for block in expected_block]
    assert resident.count(0) == 1, f"exactly one block must be evicted: {resident}"
    evicted_index = resident.index(0)
    before = len(agent.acquires)
    await agent.send(make_fetch(addresses[evicted_index], 15))
    assert len(agent.acquires) == before + 1, "the evicted block must miss again"

    # The most recently touched block is still a hit.
    before = len(agent.acquires)
    await agent.send(make_fetch(first, 15))
    assert len(agent.acquires) == before


@pytest.mark.feature("ICACHE-ICACHE-006")
async def test_replacement_does_not_disturb_other_sets(icache_agent):
    agent = icache_agent
    set_a = 0x20
    set_b = 0x21
    a0 = same_set_vaddr(set_a, 0)
    b0 = same_set_vaddr(set_b, 0)
    await agent.send(make_fetch(a0, 15))
    await agent.send(make_fetch(b0, 15))
    # Fill set A completely.
    for tag in range(1, 5):
        await agent.send(make_fetch(same_set_vaddr(set_a, tag), 15))
    # Set B must be untouched.
    before = len(agent.acquires)
    observed = await agent.send(make_fetch(b0, 15))
    assert len(agent.acquires) == before
    # A 32-byte fetch reads only banks 0..3; the refill path fills all eight.
    assert (observed.blocks[0].data & ((1 << 256) - 1)
            == model.memory_data(b0 >> 6) & ((1 << 256) - 1))


@pytest.mark.feature("ICACHE-ICACHE-007")
async def test_fence_i_invalidates_the_whole_cache(icache_agent):
    agent = icache_agent
    address = 0x6000
    await agent.send(make_fetch(address, 15))
    before = len(agent.acquires)
    await agent.send(make_fetch(address, 15))
    assert len(agent.acquires) == before, "warm-up check: the block is resident"

    await agent.fence_i()
    observed = await agent.send(make_fetch(address, 15))
    assert len(agent.acquires) == before + 1, (
        "fence.i must force the instruction stream to be re-fetched")
    assert (observed.blocks[0].data & ((1 << 256) - 1)
            == model.memory_data(address >> 6) & ((1 << 256) - 1))


@pytest.mark.feature("ICACHE-ICACHE-008")
async def test_redirect_flush_drops_the_in_flight_fetch(icache_agent):
    agent = icache_agent
    address = 0x7000
    req = make_fetch(address, 15)
    itlb = agent.itlb_translate(address)

    expected = agent.model.expect(
        req, model.mp.FetchRequest(0, 0, 0, 0, valid=0), itlb=itlb)
    agent.expected_fills = dict(expected.fill_by_block)
    agent.auto_memory = True

    await agent._accept_fetch(req, model.mp.FetchRequest(0, 0, 0, 0, valid=0), 0)
    await agent.wait_for(lambda: agent.mem_a_valid() == 1,
                         what="the miss acquire")
    # Hold the redirect through the refill: the miss unit must neither publish
    # a response nor write the array.
    agent.redirect_driver.set({"flush": 1})
    for _ in range(12):
        assert agent.ifu_valid() == 0, "a flushed fetch must not reach the IFU"
        await agent._edge()
    agent.redirect_driver.set({"flush": 0})
    for _ in range(4):
        assert agent.ifu_valid() == 0
        await agent._edge()

    # The line was never written, so the next fetch must miss and succeed.
    agent.expected_fills = {}
    observed = await agent.send(req)
    assert (observed.blocks[0].data & ((1 << 256) - 1)
            == model.memory_data(address >> 6) & ((1 << 256) - 1))


@pytest.mark.feature("ICACHE-ICACHE-024")
async def test_a_way_hit_on_the_second_half_reads_the_right_banks(icache_agent):
    """Each way of a set must select its own data banks for a 0x20-offset fetch.

    A fetch starting at offset 0x20 reads banks 4..7 of the line.  Hitting way
    0..3 in turn proves the per-way, per-bank read select of the data array.
    """
    agent = icache_agent
    set_index = 0x50
    addresses = [same_set_vaddr(set_index, tag) for tag in range(4)]
    for address in addresses:
        await agent.send(make_fetch(address, 15))
    ways = set()
    for address in addresses:
        block = address >> 6
        way = agent.model.hit_way(block, set_index)
        ways.add(way)
        # 0x20 is inside the same line and does not change the set index.
        req = make_fetch(address + 0x20, 15)
        observed = await agent.send(req)
        assert observed.raw_hits[0] == 1, f"way {way} did not hit"
        assert (observed.blocks[0].data >> 256
                == (model.memory_data(block) >> 256))
    assert ways == {0, 1, 2, 3}
    # Offset 0 selects banks 0..3: hitting every way again covers the low-bank
    # per-way read select as well.
    for address in addresses:
        block = address >> 6
        observed = await agent.send(make_fetch(address, 15))
        assert observed.raw_hits[0] == 1
        assert (observed.blocks[0].data & ((1 << 256) - 1)
                == (model.memory_data(block) & ((1 << 256) - 1)))
