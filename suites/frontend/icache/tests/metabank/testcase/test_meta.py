"""Metadata and validity semantics of ICacheMetaInterleavedBank."""

from __future__ import annotations

import pytest

from icacheverify.metabank.model.bank import MetaEntry
from icacheverify.metabank.model.bank import MetaWay


@pytest.mark.feature("ICACHE-METABANK-001")
async def test_waymask_writes_and_validates_exactly_the_selected_ways(metabank_agent):
    agent = metabank_agent
    await agent.write(0x08, 0b0101, phy_tag=0x1234, maybe_rvc_map=0xFFFF, code=1)
    entries = await agent.check_read(0x08)
    assert entries[0] == MetaWay(1, MetaEntry(0x1234, 0xFFFF, 1))
    assert entries[1] == MetaWay(0, MetaEntry(0, 0, 0))
    assert entries[2] == MetaWay(1, MetaEntry(0x1234, 0xFFFF, 1))
    assert entries[3] == MetaWay(0, MetaEntry(0, 0, 0))


@pytest.mark.feature("ICACHE-METABANK-002")
async def test_valid_bits_gate_a_stale_tag(metabank_agent):
    agent = metabank_agent
    await agent.write(0x10, 0b0010, phy_tag=0xAB, maybe_rvc_map=0x1, code=0)
    await agent.flush_all()
    entries = await agent.check_read(0x10)
    assert all(entry.valid == 0 for entry in entries), "invalidate must clear every valid bit"


@pytest.mark.feature("ICACHE-METABANK-003")
async def test_flush_all_clears_every_set(metabank_agent):
    agent = metabank_agent
    for set_index in (0, 1, 0x3F, 0x7F):
        await agent.write(set_index, 0b1111, phy_tag=set_index + 1)
    await agent.flush_all()
    for set_index in (0, 1, 0x3F, 0x7F):
        entries = await agent.check_read(set_index)
        assert all(entry.valid == 0 for entry in entries), f"set {set_index} not invalidated"
    # A refill after the invalidate must work again.
    await agent.write(0x3F, 0b0001, phy_tag=0x77)
    entries = await agent.check_read(0x3F)
    assert entries[0] == MetaWay(1, MetaEntry(0x77, 0, 0))


@pytest.mark.feature("ICACHE-METABANK-004")
async def test_sets_are_independent(metabank_agent):
    agent = metabank_agent
    for set_index in range(0, 128, 7):
        await agent.write(set_index, 0b1111, phy_tag=0x1000 + set_index, code=set_index & 1)
    for set_index in range(0, 128, 7):
        entries = await agent.check_read(set_index)
        assert [entry.entry.phy_tag for entry in entries] == [0x1000 + set_index] * 4
        assert [entry.valid for entry in entries] == [1, 1, 1, 1]


@pytest.mark.feature("ICACHE-METABANK-005")
async def test_metadata_and_code_are_stored_verbatim(metabank_agent):
    agent = metabank_agent
    # A deliberately wrong parity bit must read back unchanged.
    await agent.write(0x20, 0b0010, phy_tag=0xDEADBEEF, maybe_rvc_map=0xA5A5A5A5, code=1)
    entries = await agent.check_read(0x20)
    assert entries[1] == MetaWay(1, MetaEntry(0xDEADBEEF, 0xA5A5A5A5, 1))


@pytest.mark.feature("ICACHE-METABANK-006")
async def test_read_ready_drops_while_a_write_is_offered(metabank_agent):
    agent = metabank_agent
    await agent.write(0x30, 0b0001, phy_tag=0x1)
    agent.start_write(0x31, 0b0001, phy_tag=0x2)
    try:
        await agent._edge()
        assert agent.read_ready() == 0, "a write in flight must block the read port"
        assert agent.write_ready() == 1
    finally:
        agent.stop_write()
        await agent._edge()
    await agent.wait_for(lambda: agent.read_ready() == 1, what="read ready to return")


@pytest.mark.feature("ICACHE-METABANK-007")
async def test_every_set_index_is_writable_and_readable(metabank_agent):
    """Sweep the whole 128-set range with a single way each.

    The validity array decodes one set index per write, so a partial decode
    would silently drop refills for part of the set space.
    """
    agent = metabank_agent
    for set_index in range(agent.model.sets):
        await agent.write(set_index, 0b0001, phy_tag=0x2000 + set_index,
                          code=set_index & 1)
    for set_index in range(agent.model.sets):
        entries = (await agent.check_read(set_index))
        assert entries[0] == MetaWay(1, MetaEntry(0x2000 + set_index, 0, set_index & 1)), (
            f"set {set_index} lost its refill")
        assert [way.valid for way in entries[1:]] == [0, 0, 0], (
            f"set {set_index} marked unwritten ways valid")


@pytest.mark.feature("ICACHE-METABANK-010")
async def test_reset_invalidates_every_set(metabank_agent):
    """Reset clears the validity array and the tag storage."""
    agent = metabank_agent
    for set_index in range(agent.model.sets):
        await agent.write(set_index, 0b1111, phy_tag=0x3000 + set_index,
                          maybe_rvc_map=0x1234_5678, code=1)
    await agent.reset()
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the reset sweep to finish")
    for set_index in range(agent.model.sets):
        entries = await agent.check_read(set_index)
        assert [entry.valid for entry in entries] == [0, 0, 0, 0], (
            f"set {set_index} kept a valid way after reset")


@pytest.mark.feature("ICACHE-METABANK-011")
async def test_flush_all_wins_over_a_write_in_the_same_cycle(metabank_agent):
    """A refill racing with the full invalidate must not survive it.

    ``flushAll`` is the fence.i path: after it, no stale line may remain valid.
    The RTL gives the invalidate priority over the write port, so a write
    presented in the same cycle is discarded instead of re-validating an entry.
    If the write won, a refill could install a line that outlives the flush.
    """
    agent = metabank_agent
    await agent.write(0x20, 0b0001, phy_tag=0x111)
    # Present a write and the full invalidate on the same edge.
    agent.start_write(0x21, 0b0001, phy_tag=0x222)
    agent.flush_driver.set({"flushAll": 1})
    await agent._edge()
    agent.stop_write()
    agent.flush_driver.set({"flushAll": 0})
    agent.model.flush_all()
    await agent._edge()
    await agent._edge()

    entries = await agent.check_read(0x20)
    assert all(entry.valid == 0 for entry in entries), (
        "the flushed set must stay invalid")
    entries = await agent.check_read(0x21)
    assert all(entry.valid == 0 for entry in entries), (
        "a write racing with flushAll must not leave a valid entry behind")

    # The write port must be usable again after the invalidate.
    await agent.write(0x21, 0b0001, phy_tag=0x333)
    entries = await agent.check_read(0x21)
    assert entries[0].valid == 1 and entries[0].entry.phy_tag == 0x333


@pytest.mark.feature("ICACHE-METABANK-011")
async def test_read_is_blocked_while_the_full_invalidate_is_asserted(metabank_agent):
    """The invalidate occupies the single SRAM port, so reads must wait.

    ``read.ready`` is gated by both ``write.valid`` and ``flushAll``.  A read
    accepted during the invalidate would sample a line that is being cleared;
    the ready contract must prevent that instead of relying on the consumer to
    discard the response.
    """
    agent = metabank_agent
    await agent.write(0x22, 0b0001, phy_tag=0x444)

    agent.flush_driver.set({"flushAll": 1})
    await agent._edge()
    assert agent.read_ready() == 0, (
        "a read must not be accepted while flushAll is asserted")
    await agent._edge()
    assert agent.read_ready() == 0
    agent.flush_driver.set({"flushAll": 0})
    agent.model.flush_all()
    await agent._edge()
    assert agent.read_ready() == 1, "the read port must reopen after the flush"

    entries = await agent.check_read(0x22)
    assert all(entry.valid == 0 for entry in entries)
