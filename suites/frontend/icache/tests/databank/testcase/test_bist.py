"""Each data-bank SRAM way is testable through the MBIST port.

The bank owns four SRAM macros, one per way.  The memory-BIST port must be able
to select one way at a time, write a word and read it back through the test
port, and a broadcast command must reach all four ways.  Because the test port
writes the same macros the functional read path reads, a test-written word is
also visible to a normal read - that is what makes the test port useful for
array repair.
"""

from __future__ import annotations

import pytest

from suites.frontend.icache.databank.model.bank import DataEntry


SET = 0x5A
# The first way's SRAM is selected by array value 4 in this bank instance.
ARRAY_BASE = 4


@pytest.mark.feature("ICACHE-DATABANK-006")
async def test_bist_port_reaches_each_way(databank_agent):
    agent = databank_agent
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")

    for way in range(4):
        data = 0xB000_0000_0000_0000 | way
        word = ((data << 2) | (1 << 1)) & ((1 << 66) - 1)
        ack, _ = await agent.bist_command(
            array=ARRAY_BASE + way, readen=0, writeen=1, be=1,
            addr=SET, addr_rd=SET, indata=word)
        assert ack == 1, f"way {way} did not acknowledge the BIST write"

    for way in range(4):
        data = 0xB000_0000_0000_0000 | way
        agent.model.write(SET, 1 << way, DataEntry(data, 1))
    entries = await agent.check_read(SET)
    assert [entry.data for entry in entries] == [
        0xB000_0000_0000_0000 | way for way in range(4)]
    assert all(entry.code == 1 for entry in entries)


@pytest.mark.feature("ICACHE-DATABANK-006")
async def test_bist_broadcast_covers_all_ways(databank_agent):
    agent = databank_agent
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")
    set_index = SET + 1
    data = 0xC0DE_0000_0000_0001
    word = ((data << 2) | (1 << 1)) & ((1 << 66) - 1)
    ack, _ = await agent.bist_command(
        all_arrays=1, readen=0, writeen=1, be=1,
        addr=set_index, addr_rd=set_index, indata=word)
    assert ack == 1
    agent.model.write(set_index, 0b1111, DataEntry(data, 1))
    entries = await agent.check_read(set_index)
    assert [entry.data for entry in entries] == [data] * 4


@pytest.mark.feature("ICACHE-DATABANK-006")
async def test_bist_port_reads_back_a_written_word(databank_agent):
    """The test port itself must read back what it wrote, way by way."""
    agent = databank_agent
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")
    for way in range(4):
        set_index = 0x60 + way
        data = 0xE000_0000_0000_0000 | way
        word = ((data << 2) | ((way & 1) << 1)) & ((1 << 66) - 1)
        ack, _ = await agent.bist_command(
            array=ARRAY_BASE + way, readen=0, writeen=1, be=1,
            addr=set_index, addr_rd=set_index, indata=word)
        assert ack == 1
        ack, out = await agent.bist_command(
            array=ARRAY_BASE + way, readen=1, writeen=0,
            addr_rd=set_index)
        assert ack == 1
        assert out == word, f"way {way} read back {out:#x} != {word:#x}"


@pytest.mark.feature("ICACHE-DATABANK-006")
async def test_bist_broadcast_then_specific_select_clears_the_broadcast(databank_agent):
    agent = databank_agent
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")
    ack, _ = await agent.bist_command(all_arrays=1, readen=0, writeen=1, be=1,
                                      addr=0x22, addr_rd=0x22, indata=0x1111)
    assert ack == 1
    ack, _ = await agent.bist_command(array=ARRAY_BASE + 3, readen=0,
                                      writeen=1, be=1, addr=0x23,
                                      addr_rd=0x23, indata=0x2222)
    assert ack == 1
    ack, out = await agent.bist_command(array=ARRAY_BASE + 3, readen=1,
                                        writeen=0, addr_rd=0x23)
    assert ack == 1 and out == 0x2222
    # Move the array select off the last way so the decoded one-hot drops.
    ack, _ = await agent.bist_command(array=ARRAY_BASE, readen=0, writeen=1,
                                      be=1, addr=0x24, addr_rd=0x24,
                                      indata=0x3333)
    assert ack == 1
    ack, out = await agent.bist_command(array=ARRAY_BASE, readen=1,
                                        writeen=0, addr_rd=0x24)
    assert ack == 1 and out == 0x3333
