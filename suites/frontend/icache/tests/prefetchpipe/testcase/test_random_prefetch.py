"""Random legal prefetch blocks are predicted from the metadata array.

The prefetch pipe is a pure lookup path: any legal FTQ block, any hit way and
any 32-bit RVC map/parity bit must produce the way-lookup entry the model
predicts.  Random addresses cover all set indices, both meta ports and
cross-line selections.
"""

from __future__ import annotations

import random

import pytest

from suites.frontend.icache.prefetchpipe.model.prefetchpipe import MetaEntry
from suites.frontend.icache.prefetchpipe.model.prefetchpipe import PrefetchRequest
from suites.frontend.icache.prefetchpipe.model import prefetchpipe as model


PTAG = 0x23456


def random_block(rng: random.Random) -> tuple[int, int]:
    # The fetch block start may lie anywhere in the 64-byte line at a 2-byte
    # boundary (0x20..0x3E is the cross-line half), and the end offset must be
    # at or after the start's offset inside the 32-byte fetch window.
    start = rng.choice(range(0, 64, 2))
    low = start & 0x1F
    end = rng.choice([value for value in range(1, 32, 2) if value >= low])
    vaddr = ((rng.getrandbits(50) & ~0x3F) | start) & ((1 << 50) - 1)
    return vaddr, end


def hit_meta_random(rng: random.Random,
                    ptag: int = PTAG) -> tuple[tuple[MetaEntry, ...], ...]:
    way = rng.randrange(model.WAYS)
    entries = tuple(
        MetaEntry(ptag=ptag if index == way else (ptag + 1 + index) & ((1 << 36) - 1),
                  rvc=rng.getrandbits(32) if index == way else 0,
                  code=rng.getrandbits(1) if index == way else 0)
        for index in range(model.WAYS))
    return (entries, entries)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-001")
async def test_random_prefetch_blocks_are_predicted(prefetchpipe_agent):
    agent = prefetchpipe_agent
    rng = random.Random(0x9F3C_4A11)
    for _ in range(64):
        vaddr, end = random_block(rng)
        req = PrefetchRequest(
            vaddr=vaddr, next_vaddr=vaddr + 64, end_position=end,
            ftq_idx=rng.getrandbits(6),
            is_cross_line=model.is_cross_line(vaddr, end),
            is_soft_prefetch=0, backend_exception=0,
            vset=(model.get_idx(vaddr), model.get_idx(vaddr + 64)))
        # Any physical address and any guest physical address are legal ITLB
        # outputs; the metadata entries use the matching page tag, and random
        # PF/GPF/AF pins drive the exception payload as well.
        paddr = rng.getrandbits(48)
        meta = hit_meta_random(rng, paddr >> model.PAGE_OFF_BITS)
        itlb = model.ItlbResponse(
            miss=0, paddr=paddr, gpaddr=rng.getrandbits(55),
            pf=rng.getrandbits(1), gpf=rng.getrandbits(1),
            af=rng.getrandbits(1), pbmt=rng.randrange(3),
            vs_non_leaf=rng.getrandbits(1))
        await agent.send(req, itlb=itlb, meta=meta)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-009")
async def test_random_dual_prefetch_pairs_are_predicted(prefetchpipe_agent):
    """Random interleaved pairs drive the second request/read-port payload.

    A single-prefetch stream leaves every request-1 field and the second
    metadata port constant.  Interleave is a legal case for two blocks in
    different parity banks, so both requests are accepted and both writes are
    checked against the model.
    """
    agent = prefetchpipe_agent
    rng = random.Random(0x9F3C_7A11)
    for _ in range(32):
        vaddr0 = ((rng.getrandbits(50) & ~0x7F) | 0x000) & ((1 << 50) - 1)
        vaddr1 = ((rng.getrandbits(50) & ~0x7F) | 0x040) & ((1 << 50) - 1)
        requests = []
        for index, vaddr in enumerate((vaddr0, vaddr1)):
            requests.append(PrefetchRequest(
                vaddr=vaddr, next_vaddr=vaddr + 64, end_position=15,
                ftq_idx=rng.getrandbits(6),
                is_cross_line=0, is_soft_prefetch=0, backend_exception=0,
                vset=(model.get_idx(vaddr), model.get_idx(vaddr + 64))))
        # The two blocks must be in different parity banks for Interleave.
        requests[1] = PrefetchRequest(
            vaddr=requests[1].vaddr, next_vaddr=requests[1].next_vaddr,
            end_position=requests[1].end_position,
            ftq_idx=requests[1].ftq_idx, is_cross_line=0,
            is_soft_prefetch=0, backend_exception=0,
            vset=(requests[0].vset[0] + 1, requests[0].vset[0] + 2))
        meta = hit_meta_random(rng)
        await agent.send(*requests, case=model.CASE_INTERLEAVE,
                         itlb=model.ItlbResponse(miss=0, paddr=PTAG << 12),
                         meta=meta)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-009")
async def test_random_double_line_pairs_carry_the_second_map(prefetchpipe_agent):
    """Same-line cross fetches read both metadata ports and both RVC maps.

    A non-cross single fetch never samples the second port, so the second 32-bit
    map slot stays constant.  A same-line pair whose first block crosses the
    line reads port 0 for the first line and port 1 for the next, and both maps
    must reach the way-lookup entry unchanged.
    """
    agent = prefetchpipe_agent
    rng = random.Random(0x9F3C_D0B1)
    for _ in range(12):
        base = rng.getrandbits(50) & ~0xFFF
        vaddr0 = base | 0x20 | (rng.randrange(0x20) & ~1)
        vaddr1 = (vaddr0 & ~0x3F) | (rng.randrange(32) & ~1)
        req0 = PrefetchRequest(
            vaddr=vaddr0, next_vaddr=vaddr0 + 64, end_position=31,
            ftq_idx=rng.getrandbits(6), is_cross_line=1,
            is_soft_prefetch=0, backend_exception=0,
            vset=(model.get_idx(vaddr0), model.get_idx(vaddr0 + 64)))
        req1 = PrefetchRequest(
            vaddr=vaddr1, next_vaddr=vaddr1 + 64, end_position=15,
            ftq_idx=rng.getrandbits(6), is_cross_line=0,
            is_soft_prefetch=0, backend_exception=0,
            vset=(model.get_idx(vaddr1), model.get_idx(vaddr1 + 64)))
        paddr = rng.getrandbits(48)
        meta = hit_meta_random(rng, paddr >> model.PAGE_OFF_BITS)
        await agent.send(req0, req1, case=model.CASE_SAME_LINE,
                         itlb=model.ItlbResponse(miss=0, paddr=paddr),
                         meta=meta)
