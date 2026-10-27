"""Refill-completion metadata update and its read hazard.

A way-lookup memo records the set/way a TLB lookup predicted for a block. When
the miss unit completes a refill, that memo must be corrected: same tag adopts
the filled way, a different tag that occupies the memoised way invalidates it,
and while the memo is being rewritten it must not be handed downstream.
"""

from __future__ import annotations

import pytest

from icacheverify.waylookup.case.definitions import entry_for_block


def blk(paddr: int) -> int:
    """Block address (``pAddr >> 6``) as the DUT's ``blkPAddr`` port expects."""
    return paddr >> 6


@pytest.mark.feature("ICACHE-WAYLOOKUP-008")
async def test_refill_with_same_tag_adopts_filled_way(waylookup_agent):
    agent = waylookup_agent
    address = 0x1234_5000
    block = blk(address)
    # The TLB lookup guessed way 1; the refill actually lands in way 4.
    agent.expect_empty()
    await agent.write(entry_for_block(block, waymask=0b0001), ftq_value=1)

    await agent.refill(block, waymask=0b1000, maybe_rvc_map=0xA5)
    resident = agent.resident(1)
    assert resident[0].waymask == 0b1000, "matching tag must adopt the filled way"
    assert resident[0].maybe_rvc_map == 0xA5, "matching tag must adopt the RVC map"

    beat = (await agent.read_beats(1))[0]
    assert beat.entry.waymask[0] == 0b1000
    assert beat.entry.maybe_rvc_map[0] == 0xA5


@pytest.mark.feature("ICACHE-WAYLOOKUP-008")
async def test_refill_with_other_tag_invalidates_the_claimed_way(waylookup_agent):
    agent = waylookup_agent
    block = blk(0x2000_0000)
    # A 0x4000 offset changes physical-tag bits without touching pAddr[13:6],
    # so this block lands in the same set with a different tag.
    other = blk(0x2000_4000)
    await agent.write(entry_for_block(block, waymask=0b0010), ftq_value=2)

    await agent.refill(other, waymask=0b0010)
    resident = agent.resident(1)
    assert resident[0].waymask == 0, "a replaced way must be invalidated in the memo"

    beat = (await agent.read_beats(1))[0]
    assert beat.entry.waymask[0] == 0, "downstream must observe the invalidation"


@pytest.mark.feature("ICACHE-WAYLOOKUP-008")
async def test_unrelated_refill_leaves_the_memo_intact(waylookup_agent):
    agent = waylookup_agent
    block = blk(0x3000_0000)
    other_set = blk(0x3000_1000)
    await agent.write(entry_for_block(block, waymask=0b0100), ftq_value=3)

    await agent.refill(other_set, waymask=0b0100)
    resident = agent.resident(1)
    assert resident[0].waymask == 0b0100, "an unrelated set must not disturb the memo"

    beat = (await agent.read_beats(1))[0]
    assert beat.entry.waymask[0] == 0b0100


@pytest.mark.feature("ICACHE-WAYLOOKUP-009")
async def test_reading_is_suppressed_while_the_memo_is_rewritten(waylookup_agent):
    """Read-after-write hazard: the rewritten entry is held back one cycle."""
    agent = waylookup_agent
    block = blk(0x4000_0000)
    await agent.write(entry_for_block(block, waymask=0b0001), ftq_value=4)

    observed = await agent.refill_and_observe_read(block, waymask=0b0010)
    assert observed == 0, "the entry under update must not be presented downstream"

    # After the update settles the entry is readable again with fresh metadata.
    beat = (await agent.read_beats(1))[0]
    assert beat.entry.waymask[0] == 0b0010
