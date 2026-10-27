"""The tag SRAM is testable through the MBIST port.

The bank owns one tag macro.  A memory-BIST write must be captured by that
macro and be readable through the test port, so the array can be tested without
running the cache pipeline.
"""

from __future__ import annotations

import pytest


@pytest.mark.feature("ICACHE-METABANK-008")
async def test_bist_port_reaches_the_tag_array(metabank_agent):
    agent = metabank_agent
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")
    addr = 0x2D
    word = 0x1_2345_6789_ABCD_EF01 & ((1 << 138) - 1)
    ack, _ = await agent.bist_command(
        array=0, readen=0, writeen=1, be=0b11,
        addr=addr, addr_rd=addr, indata=word)
    assert ack == 1, "the tag array did not acknowledge the BIST write"
    ack, out = await agent.bist_command(
        array=0, readen=1, writeen=0, addr_rd=addr)
    assert ack == 1, "the tag array did not acknowledge the BIST read"
    assert out == word, "the BIST read did not return the written word"


@pytest.mark.feature("ICACHE-METABANK-008")
async def test_bist_broadcast_selects_the_banks_macro(metabank_agent):
    """A broadcast command reaches the bank's tag macro.

    The bank owns a single tag macro, so ``all`` must reach it just like the
    explicit array select; the value is read back through the test port.
    """
    agent = metabank_agent
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")
    addr = 0x11
    word = 0x0_1357_9BDF_2468_ACE0_1234_5678_9ABC & ((1 << 138) - 1)
    ack, _ = await agent.bist_command(
        all_arrays=1, readen=0, writeen=1, be=0b11,
        addr=addr, addr_rd=addr, indata=word)
    assert ack == 1
    ack, out = await agent.bist_command(
        all_arrays=1, readen=1, writeen=0, addr_rd=addr)
    assert ack == 1
    assert out == word


@pytest.mark.feature("ICACHE-METABANK-008")
async def test_bist_broadcast_then_specific_select_clears_the_broadcast(metabank_agent):
    """After a broadcast command the select must return to one array.

    ``allReg`` and the selected-one-hot vector stay high after a broadcast; a
    following per-array command has to drop them, otherwise the next test
    command would hit every array.
    """
    agent = metabank_agent
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")
    ack, _ = await agent.bist_command(all_arrays=1, readen=0, writeen=1,
                                      be=0b11, addr=0x20, addr_rd=0x20,
                                      indata=0x1234)
    assert ack == 1
    ack, _ = await agent.bist_command(array=0, readen=0, writeen=1, be=0b11,
                                      addr=0x21, addr_rd=0x21, indata=0x5678)
    assert ack == 1
    ack, out = await agent.bist_command(array=0, readen=1, writeen=0,
                                        addr_rd=0x21)
    assert ack == 1 and out == 0x5678
