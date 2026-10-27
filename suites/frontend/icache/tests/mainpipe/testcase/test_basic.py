"""Main pipe request/response handshake."""

from __future__ import annotations

import pytest

from icacheverify.mainpipe.case.definitions import make_fetch
from icacheverify.mainpipe.case.definitions import data_word
from icacheverify.mainpipe.case.definitions import make_way
from icacheverify.mainpipe.model import mainpipe as model

PTAG = 0x23456


@pytest.mark.feature("ICACHE-MAINPIPE-001")
async def test_ifu_backpressure_holds_the_response(mainpipe_agent):
    """A response stays valid until the IFU accepts it."""
    agent = mainpipe_agent
    req = make_fetch(0x9D00, 15)
    way = make_way(req, PTAG, (0b0001, 0), rvc_map=(0, 0))
    observed = await agent.send(req, way0=way, mask_unread_banks=True,
                                ifu_stall_cycles=6)
    assert observed.ifu_valid == 1
    assert observed.blocks[0].data != 0


@pytest.mark.feature("ICACHE-MAINPIPE-002")
async def test_miss_request_is_held_under_miss_unit_backpressure(mainpipe_agent):
    """A missing fetch keeps offering the same miss until the miss unit accepts."""
    agent = mainpipe_agent
    req = make_fetch(0xA100, 15)
    way = make_way(req, PTAG, (0, 0), rvc_map=(0, 0))
    refill = model.MissResponse(
        block=model.get_blk_addr(PTAG, req.vaddr), vset=req.vset[0],
        data=data_word(req.vset[0], 0), maybe_rvc_map=0xFFFF_FFFF)
    observed = await agent.send(req, way0=way, refill=refill,
                                miss_stall_cycles=5, mask_unread_banks=True)
    assert observed.ifu_valid == 1
