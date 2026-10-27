"""Random metadata, parity and way masks are stored verbatim.

Refills carry an arbitrary physical tag, RVC map and ECC bit.  Using fixed
0x1000+set tags leaves the tag's high bits constant; random legal metadata with
the independent model checks the whole 69-bit entry per way.
"""

from __future__ import annotations

import random

import pytest


@pytest.mark.feature("ICACHE-METABANK-005")
async def test_random_metadata_is_stored_verbatim(metabank_agent):
    agent = metabank_agent
    rng = random.Random(0x3E7A_B00C)
    for set_index in range(agent.model.sets):
        waymask = rng.randrange(1, 0b1111 + 1)
        await agent.write(
            set_index, waymask,
            phy_tag=rng.getrandbits(36),
            maybe_rvc_map=rng.getrandbits(32),
            code=rng.getrandbits(1))
    for set_index in range(agent.model.sets):
        await agent.check_read(set_index)


@pytest.mark.feature("ICACHE-METABANK-008")
async def test_random_words_through_the_bist_port(metabank_agent):
    """Random tag words exercise the full 138-bit MBIST write-data path."""
    agent = metabank_agent
    rng = random.Random(0x3E7A_B157)
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the macro reset sweep")
    for _ in range(16):
        set_index = rng.randrange(128)
        word = rng.getrandbits(138)
        ack, _ = await agent.bist_command(
            array=0, readen=0, writeen=1, be=0b11,
            addr=set_index, addr_rd=set_index, indata=word)
        assert ack == 1
        ack, out = await agent.bist_command(
            array=0, readen=1, writeen=0, addr_rd=set_index)
        assert ack == 1
        assert out == word
