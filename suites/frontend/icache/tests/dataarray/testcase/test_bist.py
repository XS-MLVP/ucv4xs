"""Every data bank and way is testable through the MBIST port.

Each of the eight banks owns four data macros.  The test port must select one
macro at a time, write a word and read it back; a functional read of the same
bank/way must then return the test-written word, proving the test port and the
cache's data path address the same storage.
"""

from __future__ import annotations

import pytest

from icacheverify.dataarray.model.array import DataEntry
from icacheverify.dataarray.model.array import LineSelect
from icacheverify.dataarray.model.array import ReadRequest


SET = 0x37
# Data-bank b selects its four ways with array values starting at 4 + 4*b.
def array_of(bank: int, way: int) -> int:
    return 4 + 4 * bank + way


@pytest.mark.feature("ICACHE-DATAARRAY-009")
async def test_bist_port_reaches_every_bank_and_way(dataarray_agent):
    agent = dataarray_agent
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")
    words = {}
    for bank in range(8):
        for way in range(4):
            data = (0xD000_0000_0000_0000 | (bank << 8) | way)
            word = ((data << 2) | (1 << 1)) & ((1 << 66) - 1)
            words[(bank, way)] = word
            ack, _ = await agent.bist_command(
                str(bank) if bank else "", array=array_of(bank, way),
                readen=0, writeen=1, be=1, addr=SET, addr_rd=SET,
                indata=word)
            assert ack == 1, f"bank {bank} way {way} did not acknowledge"
    for (bank, way), word in words.items():
        ack, out = await agent.bist_command(
            str(bank) if bank else "", array=array_of(bank, way),
            readen=1, writeen=0, addr_rd=SET)
        assert ack == 1
        assert out == word, f"bank {bank} way {way} read back {out:#x}"

    # One bank/way is checked through the functional read path as well.
    bank, way = 3, 2
    word = words[(bank, way)]
    agent.model.write(
        SET, 1 << way,
        tuple(DataEntry(word >> 2, (word >> 1) & 1) if b == bank
              else DataEntry(0, 0) for b in range(8)))
    request = ReadRequest(lines=(
        LineSelect(bank_mask=1 << bank, set_index=SET, waymask=1 << way),))
    values = await agent.read(request)
    assert values[0][bank].data == word >> 2
    assert values[0][bank].code == (word >> 1) & 1


@pytest.mark.feature("ICACHE-DATAARRAY-009")
async def test_bist_broadcast_writes_all_ways_of_a_bank(dataarray_agent):
    """The broadcast select writes all four ways of one bank at once.

    A bank's test port with ``all`` asserted reaches every way macro of that
    bank, which a functional read of the four ways must then observe.
    """
    agent = dataarray_agent
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")
    for bank in range(8):
        set_index = 0x80 + bank
        data = 0xF000_0000_0000_0000 | bank
        word = ((data << 2) | (1 << 1)) & ((1 << 66) - 1)
        ack, _ = await agent.bist_command(
            str(bank) if bank else "", all_arrays=1, readen=0, writeen=1,
            be=1, addr=set_index, addr_rd=set_index, indata=word)
        assert ack == 1, f"bank {bank} did not acknowledge the broadcast write"
        entry = DataEntry(word >> 2, (word >> 1) & 1)
        agent.model.write(
            set_index, 0b1111,
            tuple(entry if b == bank else DataEntry(0, 0) for b in range(8)))
        # The bank returns one way per request, so each way is read in turn.
        for way in range(4):
            request = ReadRequest(lines=(
                LineSelect(bank_mask=1 << bank, set_index=set_index,
                           waymask=1 << way),))
            values = await agent.read(request)
            assert values[0][bank] == entry, (
                f"bank {bank} way {way}: the broadcast write is not visible")
