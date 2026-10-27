"""Random bank words are routed and returned verbatim.

A refill fills all eight banks with arbitrary 64-bit words and a parity bit.
Randomising the payload (and the way mask) while the router model predicts each
bank's answer exercises the full 8x66-bit write port and every per-bank
response, which fixed line images do not.
"""

from __future__ import annotations

import random

import pytest

from icacheverify.dataarray.model.array import DataEntry
from icacheverify.dataarray.model.array import LineSelect
from icacheverify.dataarray.model.array import ReadRequest


@pytest.mark.feature("ICACHE-DATAARRAY-001")
async def test_random_bank_words_are_routed_verbatim(dataarray_agent):
    agent = dataarray_agent
    rng = random.Random(0xDA7A_A22A)
    # Random payload, exhaustive way mask: 48 samples out of 15 masks cannot
    # guarantee that every way-select combination is driven.
    masks = list(range(1, 0b1111 + 1))
    for index in range(48):
        set_index = rng.randrange(agent.model.sets)
        waymask = masks[index % len(masks)]
        entries = tuple(DataEntry(rng.getrandbits(64), rng.getrandbits(1))
                        for _ in range(agent.model.banks))
        await agent.write(set_index, waymask, entries)
        for way in range(agent.model.ways):
            if not (waymask >> way) & 1:
                continue
            for bank in range(agent.model.banks):
                request = ReadRequest(lines=(
                    LineSelect(bank_mask=1 << bank, set_index=set_index,
                               waymask=1 << way),))
                values = await agent.read(request)
                assert values[0][bank] == entries[bank], (
                    f"set {set_index} way {way} bank {bank}: "
                    f"{values[0][bank]} != {entries[bank]}")


@pytest.mark.feature("ICACHE-DATAARRAY-009")
async def test_random_words_through_every_bist_port(dataarray_agent):
    """Random test words exercise every bank's MBIST write-data path.

    Each of the eight banks has its own BIST pipeline and four way macros;
    randomising the 66-bit payload covers the per-bank registers and write-data
    wires that a single fixed pattern leaves constant.
    """
    agent = dataarray_agent
    rng = random.Random(0xB157_A22A)
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")
    for bank in range(agent.model.banks):
        child = str(bank) if bank else ""
        for way in range(agent.model.ways):
            for _ in range(3):
                set_index = rng.randrange(agent.model.sets)
                word = rng.getrandbits(66)
                ack, _ = await agent.bist_command(
                    child, array=4 + 4 * bank + way, readen=0, writeen=1,
                    be=1, addr=set_index, addr_rd=set_index, indata=word)
                assert ack == 1
                ack, out = await agent.bist_command(
                    child, array=4 + 4 * bank + way, readen=1, writeen=0,
                    addr_rd=set_index)
                assert ack == 1
                assert out == word, (
                    f"bank {bank} way {way} read back {out:#x} != {word:#x}")


@pytest.mark.feature("ICACHE-DATAARRAY-004")
async def test_random_dual_requests_use_both_response_slots(dataarray_agent):
    """Two requests in one cycle drive the second read/response slot's payload."""
    agent = dataarray_agent
    rng = random.Random(0xDA7A_D0A1)
    written = {}
    for _ in range(16):
        set_index = rng.randrange(agent.model.sets)
        waymask = rng.randrange(1, 0b1111 + 1)
        entries = tuple(DataEntry(rng.getrandbits(64), rng.getrandbits(1))
                        for _ in range(agent.model.banks))
        await agent.write(set_index, waymask, entries)
        written[set_index] = (waymask, entries)
    for set_index, (waymask, entries) in written.items():
        ways = [way for way in range(4) if (waymask >> way) & 1]
        first_way, second_way = ways[0], ways[-1]
        first = ReadRequest(lines=(
            LineSelect(bank_mask=0xFF, set_index=set_index,
                       waymask=1 << first_way),))
        second = ReadRequest(lines=(
            LineSelect(bank_mask=0xFF, set_index=set_index,
                       waymask=1 << second_way),))
        values = await agent.read(first, second)
        for bank in range(agent.model.banks):
            assert values[0][bank] == entries[bank]
            assert values[1][bank] == entries[bank]
