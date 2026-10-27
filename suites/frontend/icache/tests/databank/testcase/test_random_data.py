"""Random data words are stored and returned verbatim.

A handful of fixed patterns only exercises the low bits of the 64-bit entry and
the ECC bit.  Constrained-random refill data (64 random data bits plus a random
code) is exactly what the array sees in normal operation, and the reference
model predicts every way independently, so randomising the payload is a
functional check rather than a coverage trick.
"""

from __future__ import annotations

import random

import pytest


@pytest.mark.feature("ICACHE-DATABANK-004")
async def test_random_entries_are_stored_verbatim(databank_agent):
    agent = databank_agent
    rng = random.Random(0xDA7A_B00C)
    touched: set[int] = set()
    # The payload and the set index are random, but the way mask is swept
    # exhaustively: sampling 32 masks from a 15-value domain leaves some of
    # them unreachable for a given seed, and the way-select wires for the
    # missing masks would then never be exercised.
    masks = list(range(1, 0b1111 + 1))
    for index in range(32):
        set_index = rng.randrange(agent.model.sets)
        waymask = masks[index % len(masks)]
        data = rng.getrandbits(64)
        code = rng.getrandbits(1)
        await agent.write(set_index, waymask, data=data, code=code)
        touched.add(set_index)
    for set_index in sorted(touched):
        await agent.check_read(set_index)


@pytest.mark.feature("ICACHE-DATABANK-006")
async def test_random_words_through_the_bist_port(databank_agent):
    """Random test words exercise the full MBIST write-data path.

    The test port is the only way to write one way without disturbing the
    others; randomising its 66-bit payload covers the BIST pipeline registers
    and the per-way write-data wires, and the read-back proves the data landed.
    """
    agent = databank_agent
    rng = random.Random(0xB157_DA7A)
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")
    for way in range(4):
        for _ in range(4):
            set_index = rng.randrange(agent.model.sets)
            word = rng.getrandbits(66)
            ack, _ = await agent.bist_command(
                array=4 + way, readen=0, writeen=1, be=1,
                addr=set_index, addr_rd=set_index, indata=word)
            assert ack == 1
            ack, out = await agent.bist_command(
                array=4 + way, readen=1, writeen=0, addr_rd=set_index)
            assert ack == 1
            assert out == word, f"way {way} read back {out:#x} != {word:#x}"
