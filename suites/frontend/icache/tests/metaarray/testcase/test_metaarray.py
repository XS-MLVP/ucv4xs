"""Metadata array semantics, including interleaved-bank routing."""

from __future__ import annotations

import pytest

from icacheverify.metaarray.model.array import MetaEntry
from icacheverify.metaarray.model.array import MetaWay


@pytest.mark.feature("ICACHE-METAARRAY-001")
async def test_waymask_writes_and_validates_selected_ways(metaarray_agent):
    agent = metaarray_agent
    # Non-contiguous mask: ways 0 and 2, so an off-by-one or contiguous-mask
    # shortcut in the array would be visible.
    await agent.write(0x04, 0b0101, phy_tag=0x1234, maybe_rvc_map=0xABCD, code=1)
    entries = (await agent.check_read(0x04))[0]
    assert entries == (MetaWay(1, MetaEntry(0x1234, 0xABCD, 1)),
                          MetaWay(0, MetaEntry(0, 0, 0)),
                          MetaWay(1, MetaEntry(0x1234, 0xABCD, 1)),
                          MetaWay(0, MetaEntry(0, 0, 0)))


@pytest.mark.feature("ICACHE-METAARRAY-002")
async def test_single_line_read_returns_the_addressed_set(metaarray_agent):
    agent = metaarray_agent
    await agent.write(0x10, 0b1111, phy_tag=0xAAA)
    await agent.write(0x11, 0b1111, phy_tag=0xBBB)
    first = (await agent.check_read(0x10))[0]
    second = (await agent.check_read(0x11))[0]
    assert all(way.entry.phy_tag == 0xAAA for way in first)
    assert all(way.entry.phy_tag == 0xBBB for way in second)


@pytest.mark.feature("ICACHE-METAARRAY-003")
async def test_double_line_read_preserves_request_order(metaarray_agent):
    agent = metaarray_agent
    await agent.write(0x20, 0b1111, phy_tag=0x20)
    await agent.write(0x21, 0b1111, phy_tag=0x21)
    # Even/odd pair: the two sets live in different interleaved banks.
    lines = await agent.check_read(0x20, 0x21)
    assert [ways[0].entry.phy_tag for ways in lines] == [0x20, 0x21]
    # Reversed order must come back reversed, proving order is not by bank.
    lines = await agent.check_read(0x21, 0x20)
    assert [ways[0].entry.phy_tag for ways in lines] == [0x21, 0x20]
    # The contract only requires one set per interleaved bank, so a far-apart
    # even/odd pair must work as well as an adjacent one.
    await agent.write(0x40, 0b1111, phy_tag=0x40)
    await agent.write(0x61, 0b1111, phy_tag=0x61)
    lines = await agent.check_read(0x40, 0x61)
    assert [ways[0].entry.phy_tag for ways in lines] == [0x40, 0x61]


@pytest.mark.feature("ICACHE-METAARRAY-004")
async def test_adjacent_sets_do_not_alias_across_banks(metaarray_agent):
    agent = metaarray_agent
    for set_index in range(0, 16):
        await agent.write(set_index, 0b1111, phy_tag=0x500 + set_index)
    for set_index in range(0, 16):
        entries = (await agent.check_read(set_index))[0]
        assert [way.entry.phy_tag for way in entries] == [0x500 + set_index] * 4
    # Neighbouring sets that share a bank (0x30 and 0x32) must stay separate.
    await agent.write(0x30, 0b0001, phy_tag=0x1)
    await agent.write(0x32, 0b0001, phy_tag=0x2)
    assert (await agent.check_read(0x30))[0][0].entry.phy_tag == 0x1
    assert (await agent.check_read(0x32))[0][0].entry.phy_tag == 0x2


@pytest.mark.feature("ICACHE-METAARRAY-005")
async def test_flush_all_clears_every_valid_bit(metaarray_agent):
    agent = metaarray_agent
    for set_index in (0, 1, 0x40, 0xFF):
        await agent.write(set_index, 0b1111, phy_tag=set_index + 1)
    await agent.flush_all()
    for set_index in (0, 1, 0x40, 0xFF):
        entries = (await agent.check_read(set_index))[0]
        assert all(way.valid == 0 for way in entries), f"set {set_index} not invalidated"
    # A refill after the invalidate must work again.
    await agent.write(0xFF, 0b0001, phy_tag=0x99)
    assert (await agent.check_read(0xFF))[0][0] == MetaWay(1, MetaEntry(0x99, 0, 0))


@pytest.mark.feature("ICACHE-METAARRAY-006")
async def test_metadata_and_code_are_stored_verbatim(metaarray_agent):
    agent = metaarray_agent
    await agent.write(0x60, 0b0010, phy_tag=0xDEADBEEF, maybe_rvc_map=0x5A5A5A5A, code=1)
    entries = (await agent.check_read(0x60))[0]
    assert entries[1] == MetaWay(1, MetaEntry(0xDEADBEEF, 0x5A5A5A5A, 1))


@pytest.mark.feature("ICACHE-METAARRAY-007")
async def test_read_ready_drops_while_a_write_is_offered(metaarray_agent):
    agent = metaarray_agent
    await agent.write(0x70, 0b0001, phy_tag=0x1)
    agent.start_write(0x71, 0b0001, phy_tag=0x2)
    try:
        await agent._edge()
        assert agent.read_ready() == 0, "a write in flight must block the read port"
    finally:
        agent.stop_write()
        await agent._edge()
    await agent.wait_for(lambda: agent.read_ready() == 1, what="read ready to return")


@pytest.mark.feature("ICACHE-METAARRAY-008")
async def test_every_set_index_is_writable_and_readable(metaarray_agent):
    """Sweep the whole set range, one way per set.

    Each interleaved bank decodes its own 128 indices, so a partial decode would
    silently drop refills for part of the set space.
    """
    agent = metaarray_agent
    for set_index in range(agent.model.sets):
        await agent.write(set_index, 0b0001, phy_tag=0x1000 + set_index,
                          code=set_index & 1)
    for set_index in range(agent.model.sets):
        ways = (await agent.check_read(set_index))[0]
        assert ways[0] == MetaWay(1, MetaEntry(0x1000 + set_index, 0, set_index & 1)), (
            f"set {set_index} lost its refill")
        assert [way.valid for way in ways[1:]] == [0, 0, 0], (
            f"set {set_index} marked unwritten ways valid")


@pytest.mark.feature("ICACHE-METAARRAY-010")
async def test_every_way_of_every_set_is_set_and_cleared(metaarray_agent):
    """All 256 sets x 4 ways mark and clear their own valid bit.

    The two interleaved banks each decode 128 indices and all four ways; a
    one-way sweep would leave the per-way valid decode and most of the
    ``flushAll`` clear paths unexercised.
    """
    agent = metaarray_agent
    for set_index in range(agent.model.sets):
        for way in range(agent.model.ways):
            await agent.write(set_index, 1 << way,
                              phy_tag=0x6000 + set_index,
                              code=(set_index ^ way) & 1)
    for set_index in range(agent.model.sets):
        ways = (await agent.check_read(set_index))[0]
        assert [way.valid for way in ways] == [1, 1, 1, 1], (
            f"set {set_index} did not mark every written way valid")
        for way, entry in enumerate(ways):
            assert entry.entry == MetaEntry(0x6000 + set_index, 0,
                                            (set_index ^ way) & 1), (
                f"set {set_index} way {way} lost its entry")
    await agent.flush_all()
    for set_index in range(agent.model.sets):
        ways = (await agent.check_read(set_index))[0]
        assert [way.valid for way in ways] == [0, 0, 0, 0], (
            f"set {set_index} kept a valid way after flushAll")


@pytest.mark.feature("ICACHE-METAARRAY-011")
async def test_reset_invalidates_every_set_of_both_banks(metaarray_agent):
    agent = metaarray_agent
    for set_index in range(agent.model.sets):
        await agent.write(set_index, 0b1111, phy_tag=0x7000 + set_index,
                          maybe_rvc_map=0x0BAD_F00D, code=1)
    await agent.reset()
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the reset sweep to finish")
    for set_index in range(agent.model.sets):
        ways = (await agent.check_read(set_index))[0]
        assert [way.valid for way in ways] == [0, 0, 0, 0], (
            f"set {set_index} kept a valid way after reset")


@pytest.mark.feature("ICACHE-METAARRAY-012")
async def test_flush_all_wins_over_a_refill_across_both_banks(metaarray_agent):
    """A refill racing with the full invalidate must not survive in either bank.

    ``flushAll`` is driven by fence.i; a refill in the same cycle must be
    discarded, otherwise a line could stay valid after the flush.  Both
    interleaved banks must behave identically.
    """
    agent = metaarray_agent
    for set_index in (0x30, 0x31):
        await agent.write(set_index, 0b0001, phy_tag=0x900 + set_index)

    agent.start_write(0x32, 0b0010, phy_tag=0x999)
    agent.flush_driver.set({"flushAll": 1})
    await agent._edge()
    agent.stop_write()
    agent.flush_driver.set({"flushAll": 0})
    agent.model.flush_all()
    await agent._edge()
    await agent._edge()

    for set_index in (0x30, 0x31, 0x32):
        ways = (await agent.check_read(set_index))[0]
        assert all(way.valid == 0 for way in ways), (
            f"set {set_index} kept a valid way across the flush")

    await agent.write(0x32, 0b0010, phy_tag=0xABC)
    ways = (await agent.check_read(0x32))[0]
    assert ways[1].valid == 1 and ways[1].entry.phy_tag == 0xABC


@pytest.mark.feature("ICACHE-METAARRAY-012")
async def test_read_is_blocked_while_a_write_occupies_the_port(metaarray_agent):
    """Both interleaved banks refuse a read while a write is offered.

    The tag storage is single-port: read readiness is gated by write validity
    (and by the full invalidate).  A read accepted in the write cycle would be
    served from a word that is being overwritten.
    """
    agent = metaarray_agent
    await agent.write(0x34, 0b0001, phy_tag=0x123)
    agent.start_write(0x35, 0b0001, phy_tag=0x456)
    try:
        await agent._edge()
        assert agent.read_ready() == 0, (
            "a read must not be accepted while a write is in flight")
    finally:
        agent.stop_write()
        await agent._edge()
    await agent.wait_for(lambda: agent.read_ready() == 1, what="read ready")
    await agent.check_read(0x34)
