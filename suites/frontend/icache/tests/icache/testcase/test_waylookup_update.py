"""Refill responses correct the way lookup of fetches still in flight.

The prefetch pipe queues a way-lookup entry before the main pipe consumes it.
When that fetch misses, the refill response must rewrite the queued entry in
place: the same tag adopts the filled way, and a different tag that now owns the
way invalidates the entry.  These are the chip-level O(1) coherence rules the
way lookup exists for; a queue that is only correct at its read pointer would
leave stale ways behind.
"""

from __future__ import annotations

import pytest

from suites.frontend.icache.icache.case.definitions import make_fetch
from suites.frontend.icache.icache.model import icache as model


def same_set_vaddr(set_index: int, tag_index: int) -> int:
    """An address in ``set_index`` with physical page tag ``tag_index``."""
    ptag = (tag_index << 2) | (set_index >> 6)
    return (ptag << 12) | ((set_index & 0x3F) << 6)


@pytest.mark.feature("ICACHE-ICACHE-019")
async def test_refill_corrects_the_queued_way_lookup_entry(icache_agent):
    agent = icache_agent
    vaddr = 0x30000
    block = vaddr >> 6
    acquires = await agent.prefetch_only(make_fetch(vaddr, 15))
    assert [acq[0] for acq in acquires] == [block], (
        "the prefetch request must fetch its line")
    agent.model.install(block, model.get_idx(vaddr))
    way = agent.model.hit_way(block, model.get_idx(vaddr))
    assert way is not None

    # The queued entry was written with an empty waymask.  Only the refill's
    # in-place update can make this main-pipe fetch a hit.
    before = len(agent.acquires)
    observed = await agent.send_main_only(make_fetch(vaddr, 15))
    assert len(agent.acquires) == before, (
        "the queued entry kept an empty waymask after its line was refilled")
    assert (observed.blocks[0].data & ((1 << 256) - 1)
            == model.memory_data(block) & ((1 << 256) - 1))


@pytest.mark.feature("ICACHE-ICACHE-020")
async def test_eviction_invalidates_the_queued_way_lookup_entry(icache_agent):
    agent = icache_agent
    set_index = 0x30
    addresses = [same_set_vaddr(set_index, tag) for tag in range(4)]
    for address in addresses:
        await agent.send(make_fetch(address, 15))
    # Four fills leave the first block's way as the tree-PLRU victim.
    assert agent.model.victim(set_index) == 0
    first = addresses[0]
    first_block = first >> 6

    # Queue an entry for the resident first block: it names way 0.
    acquires = await agent.prefetch_only(make_fetch(first, 15))
    assert acquires == [], "the queued entry's line is already resident"

    # Fill a different block of the same set; it must evict the first block's
    # way and therefore invalidate the queued entry's waymask.
    replacer = same_set_vaddr(set_index, 4)
    replacer_block = replacer >> 6
    acquires = await agent.prefetch_only(make_fetch(replacer, 15))
    assert [acq[0] for acq in acquires] == [replacer_block]
    agent.model.install(replacer_block, set_index)
    assert agent.model.hit_mask(first_block, set_index) == 0, (
        "the refill must have evicted the queued line")

    # The main pipe now consumes the invalidated entry: the fetch must miss and
    # return the real line, not the block that stole the way.
    before = len(agent.acquires)
    observed = await agent.send_main_only(make_fetch(first, 15))
    assert len(agent.acquires) == before + 1, (
        "a queued entry whose way was stolen must miss")
    assert agent.acquires[-1][0] == first_block
    assert (observed.blocks[0].data & ((1 << 256) - 1)
            == model.memory_data(first_block) & ((1 << 256) - 1))
