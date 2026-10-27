"""Random metadata over the whole interleaved set space.

Each of the two banks owns 128 indices and four ways; random legal refills
exercise every tag/RVC/parity bit and every way's valid bit while the model
checks each returned entry.
"""

from __future__ import annotations

import random

import pytest


@pytest.mark.feature("ICACHE-METAARRAY-006")
async def test_random_metadata_is_stored_verbatim(metaarray_agent):
    agent = metaarray_agent
    rng = random.Random(0x3E7A_A22A)
    for set_index in range(agent.model.sets):
        waymask = rng.randrange(1, 0b1111 + 1)
        await agent.write(
            set_index, waymask,
            phy_tag=rng.getrandbits(36),
            maybe_rvc_map=rng.getrandbits(32),
            code=rng.getrandbits(1))
    for set_index in range(agent.model.sets):
        await agent.check_read(set_index)


@pytest.mark.feature("ICACHE-METAARRAY-009")
async def test_random_words_through_every_bist_port(metaarray_agent):
    """Random tag words exercise both banks' MBIST write-data paths."""
    agent = metaarray_agent
    rng = random.Random(0x3E7A_B157)
    await agent.wait_for(lambda: agent.read_ready() == 1,
                         what="the macro reset sweep")
    for child, arrays in (("", (0,)), ("1", (2, 3))):
        for array in arrays:
            for _ in range(8):
                set_index = rng.randrange(128)
                word = rng.getrandbits(138)
                ack, _ = await agent.bist_command(
                    child, array=array, readen=0, writeen=1, be=0b11,
                    addr=set_index, addr_rd=set_index, indata=word)
                assert ack == 1
                ack, out = await agent.bist_command(
                    child, array=array, readen=1, writeen=0,
                    addr_rd=set_index)
                assert ack == 1
                assert out == word, (
                    f"bank {child or '0'} array {array} read {out:#x}")
