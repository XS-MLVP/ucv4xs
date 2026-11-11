"""Each interleaved tag macro is testable through the MBIST port.

The two interleaved banks are separate SRAM macros with separate test selects.
A word written through the test port of one bank must read back from that bank's
test port, and the other bank must be unaffected.
"""

from __future__ import annotations

import pytest


# Bank 0 has a single macro selected by array 0; bank 1 selects its macro with
# array value 2.
BANKS = (("", (0,)), ("1", (2,)))


@pytest.mark.feature("ICACHE-METAARRAY-009")
async def test_bist_port_reaches_each_interleaved_bank(metaarray_agent):
    agent = metaarray_agent
    await agent.wait_for(lambda: agent.read_ready() == 1,
                         what="the macro reset sweep")
    words = {("", 0): 0x0FED_CBA9_8765_4321_0000_1111_2222_3333 & ((1 << 138) - 1),
             ("1", 2): 0x0ABC_DEF0_1234_5678_9999_8888_7777_6666 & ((1 << 138) - 1)}
    # Bank 0 selects its macro with array 0; bank 1 with array 2 or 3.  The
    # read-back mux in the MBIST pipeline only forwards the specifically
    # selected macro, so each bank is addressed by its own array value.
    for (child, arrays), word in zip(BANKS, words.values()):
        ack, _ = await agent.bist_command(
            child, array=arrays[0], readen=0, writeen=1, be=0b11,
            addr=0x3C, addr_rd=0x3C, indata=word)
        assert ack == 1, f"bank {child or '0'} did not acknowledge the write"
    for (child, arrays), word in zip(BANKS, words.values()):
        ack, out = await agent.bist_command(
            child, array=arrays[0], readen=1, writeen=0, addr_rd=0x3C)
        assert ack == 1
        assert out == word, f"bank {child or '0'} read back {out:#x}"


@pytest.mark.feature("ICACHE-METAARRAY-009")
async def test_bist_broadcast_reaches_each_bank(metaarray_agent):
    """The broadcast form must reach both interleaved banks' macros."""
    agent = metaarray_agent
    await agent.wait_for(lambda: agent.read_ready() == 1,
                         what="the macro reset sweep")
    word = 0x0_5555_AAAA_3333_CCCC_0F0F_F0F0_1234_5678 & ((1 << 138) - 1)
    for child, arrays in BANKS:
        ack, _ = await agent.bist_command(
            child, all_arrays=1, readen=0, writeen=1, be=0b11,
            addr=0x22, addr_rd=0x22, indata=word)
        assert ack == 1
    for child, arrays in BANKS:
        ack, out = await agent.bist_command(
            child, array=arrays[0], readen=1, writeen=0, addr_rd=0x22)
        assert ack == 1
        assert out == word, f"bank {child or '0'} read back {out:#x}"


@pytest.mark.feature("ICACHE-METAARRAY-009")
async def test_bist_broadcast_then_specific_select_clears_the_broadcast(metaarray_agent):
    agent = metaarray_agent
    await agent.wait_for(lambda: agent.read_ready() == 1,
                         what="the macro reset sweep")
    for child, array in (("", 0), ("1", 2)):
        ack, _ = await agent.bist_command(child, all_arrays=1, readen=0,
                                          writeen=1, be=0b11, addr=0x30,
                                          addr_rd=0x30, indata=0xAAAA)
        assert ack == 1
        ack, _ = await agent.bist_command(child, array=array, readen=0,
                                          writeen=1, be=0b11, addr=0x31,
                                          addr_rd=0x31, indata=0x5555)
        assert ack == 1
        ack, out = await agent.bist_command(child, array=array, readen=1,
                                            writeen=0, addr_rd=0x31)
        assert ack == 1 and out == 0x5555
