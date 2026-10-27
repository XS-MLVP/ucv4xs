"""Random legal fetch blocks are predicted byte-for-byte.

The FTQ names a fetch block by a start address and the last byte offset in the
block.  Any 2-byte-aligned start and any odd end offset at or after it is a
legal block, so a constrained-random stream covers every alignment, every data
bank mask, cross-line and non-cross fetches, and every 64-bit data bit while the
reference model predicts the aligned instruction map and the returned data.
"""

from __future__ import annotations

import dataclasses
import random

import pytest

from icacheverify.mainpipe.case.definitions import make_fetch
from icacheverify.mainpipe.case.definitions import make_way
from icacheverify.mainpipe.model import mainpipe as model


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


@pytest.mark.feature("ICACHE-MAINPIPE-001")
async def test_random_fetch_blocks_are_predicted(mainpipe_agent):
    agent = mainpipe_agent
    rng = random.Random(0xF37C_4A11)
    for _ in range(32):
        vaddr, end = random_block(rng)
        req = make_fetch(vaddr, end)
        cross = model.is_cross_line(vaddr, end)
        way = make_way(
            req, PTAG,
            (1 << rng.randrange(4),
             (1 << rng.randrange(4)) if cross else 0),
            rvc_map=(rng.getrandbits(32), rng.getrandbits(32)),
            words=tuple(rng.getrandbits(64) for _ in range(8)))
        # send() compares every response field against predict(); a mismatch
        # fails the test with a field-by-field diff.
        await agent.send(req, way0=way, mask_unread_banks=True)


@pytest.mark.feature("ICACHE-MAINPIPE-007")
async def test_random_two_fetch_pairs_are_predicted(mainpipe_agent):
    """Random legal pairs with disjoint banks both return their own data.

    The second fetch has its own data-read ports and response fields, so a
    single-fetch-only random stream leaves request 1's 512-bit path constant.
    Request 0 covers banks 0-3 and request 1 starts in the second half line, so
    the pair is legal even when both use the same way.
    """
    agent = mainpipe_agent
    rng = random.Random(0xF37C_7A11)
    for _ in range(24):
        vaddr0 = ((rng.getrandbits(50) & ~0x3F) | 0x00) & ((1 << 50) - 1)
        vaddr1 = ((rng.getrandbits(50) & ~0x3F) | 0x20) & ((1 << 50) - 1)
        req0 = make_fetch(vaddr0, 15, ftq_idx=rng.getrandbits(6))
        req1 = make_fetch(vaddr1, 31, ftq_idx=rng.getrandbits(6))
        way0 = make_way(
            req0, PTAG, (1 << rng.randrange(4), 0),
            rvc_map=(rng.getrandbits(32), 0),
            words=tuple(rng.getrandbits(64) for _ in range(8)))
        way1 = make_way(
            req1, PTAG, (1 << rng.randrange(4), 1 << rng.randrange(4)),
            rvc_map=(rng.getrandbits(32), rng.getrandbits(32)),
            words=tuple(rng.getrandbits(64) for _ in range(8)),
            gpaddr=rng.getrandbits(54) << 1)
        await agent.send(req0, req1, way0, way1, mask_unread_banks=True)


@pytest.mark.feature("ICACHE-MAINPIPE-002")
async def test_random_refills_return_random_line_data(mainpipe_agent):
    """Random refill lines drive every miss-data register and the response data.

    A hit reads the array image; only a refill writes the 512-bit stage-1 data
    registers and the RVC map register, so random refills are the stimulus that
    covers the other half of the data path.
    """
    agent = mainpipe_agent
    rng = random.Random(0xF37C_2EF1)
    for _ in range(24):
        vaddr = ((rng.getrandbits(50) & ~0x3F) |
                 rng.choice(range(0, 64, 2))) & ((1 << 50) - 1)
        end = rng.choice([value for value in range(1, 32, 2)
                          if value >= (vaddr & 0x1F)])
        req = make_fetch(vaddr, end)
        if model.is_cross_line(vaddr, end):
            continue
        ptag = rng.getrandbits(36)
        way = make_way(req, ptag, (0, 0), rvc_map=(0, 0))
        refill = model.MissResponse(
            block=model.get_blk_addr(ptag, vaddr), vset=req.vset[0],
            data=rng.getrandbits(512),
            maybe_rvc_map=rng.getrandbits(32))
        await agent.send(req, way0=way, refill=refill,
                         mask_unread_banks=True)


@pytest.mark.feature("ICACHE-MAINPIPE-003")
async def test_random_exception_payload_reaches_the_ifu(mainpipe_agent):
    """Random ITLB exception codes and gpAddr are forwarded for both fetches."""
    agent = mainpipe_agent
    rng = random.Random(0xF37C_E0C0)
    for _ in range(12):
        vaddr = ((rng.getrandbits(50) & ~0x3F) |
                 rng.choice(range(0, 64, 2))) & ((1 << 50) - 1)
        end = rng.choice([value for value in range(1, 32, 2)
                          if value >= (vaddr & 0x1F)])
        req = make_fetch(vaddr, end)
        way = make_way(req, PTAG, (0, 0), rvc_map=(0, 0),
                       itlb_exception=rng.randrange(1, 4),
                       gpaddr=rng.getrandbits(54) << 1)
        await agent.send(req, way0=way, mask_unread_banks=True)


@pytest.mark.feature("ICACHE-MAINPIPE-013")
async def test_bpu_stage2_redirect_kills_the_fetch_at_the_target(mainpipe_agent):
    """A stage-2 redirect at or before the request flushes it in stage 0.

    ``BpuFlushInfo.shouldFlushByStage2`` is ``!isAfter(redirect, request)``:
    the request is at or younger than the redirect and must not be fetched,
    must not request a miss and must not return to the IFU.
    """
    agent = mainpipe_agent
    req = make_fetch(0x9100, 15, ftq_idx=9)
    way = make_way(req, PTAG, (0b0001, 0), rvc_map=(0, 0))
    result = await agent.send(req, way0=way, bpu_s2=(0, 9))
    assert result is None, "the flushed fetch must not produce a response"


@pytest.mark.feature("ICACHE-MAINPIPE-013")
async def test_bpu_stage3_redirect_kills_the_fetch_at_the_target(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x9200, 15, ftq_idx=9)
    way = make_way(req, PTAG, (0b0001, 0), rvc_map=(0, 0))
    # A stale redirect one entry before the request still covers it.
    result = await agent.send(req, way0=way, bpu_s3=(0, 8))
    assert result is None


@pytest.mark.feature("ICACHE-MAINPIPE-013")
async def test_bpu_redirect_after_the_fetch_leaves_it_alone(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x9300, 15, ftq_idx=9)
    way = make_way(req, PTAG, (0b0001, 0), rvc_map=(0, 0))
    # Same flag, pointer after the request: isAfter is true, so no flush.
    # The flag-wrapped pointer (flag=1, value=0) is also after it.
    observed = await agent.send(req, way0=way, bpu_s2=(0, 10), bpu_s3=(1, 0))
    assert observed is not None and observed.ifu_valid == 1


@pytest.mark.feature("ICACHE-MAINPIPE-014")
async def test_satp_flush_tag_reaches_the_ifu(mainpipe_agent):
    """The fetch metadata carries the FTQ's satp-flush tag unchanged."""
    agent = mainpipe_agent
    req = make_fetch(0x9400, 15, has_satp_flush=1)
    way = make_way(req, PTAG, (0b0001, 0), rvc_map=(0, 0))
    observed = await agent.send(req, way0=way)
    assert observed.blocks[0].has_satp_flush == 1


@pytest.mark.feature("ICACHE-MAINPIPE-014")
async def test_second_fetch_taken_flag_reaches_the_ifu(mainpipe_agent):
    """The second fetch's taken flag becomes info_1.takenCfiOffset.valid."""
    agent = mainpipe_agent
    req0 = make_fetch(0x9500, 3, ftq_idx=1)
    req1 = make_fetch(0x9508, 15, ftq_idx=2, taken=1)
    way0 = make_way(req0, PTAG, (0b0001, 0), rvc_map=(0, 0))
    way1 = make_way(req1, PTAG, (0b0010, 0), rvc_map=(0, 0))
    observed = await agent.send(req0, req1, way0, way1,
                                mask_unread_banks=True)
    assert observed.blocks[1].valid == 1
    assert observed.blocks[1].taken_valid == 1


@pytest.mark.feature("ICACHE-MAINPIPE-009")
async def test_full_size_then_small_fetch_drives_the_range_masks(mainpipe_agent):
    """A 32-instruction fetch sets all range bits; the next fetch clears them."""
    agent = mainpipe_agent
    big = make_fetch(0x9600, 31)
    way = make_way(big, PTAG, (0b0001, 0), rvc_map=(0xFFFF_FFFF, 0))
    await agent.send(big, way0=way)
    small = make_fetch(0x9600, 1)
    way_small = make_way(small, PTAG, (0b0001, 0), rvc_map=(0xFFFF_FFFF, 0))
    observed = await agent.send(small, way0=way_small, mask_unread_banks=True)
    assert observed.total_range == 0b11


@pytest.mark.feature("ICACHE-MAINPIPE-013")
async def test_bpu_redirect_pointer_sweep(mainpipe_agent):
    """Sweep both pointers so every flag/value bit and both wrap directions run."""
    agent = mainpipe_agent
    ftq = 9
    for flag in (0, 1):
        for value in (0, 1, 2, 4, 8, 9, 10, 16, 31, 32, 63):
            req = make_fetch(0x9700, 15, ftq_idx=ftq)
            way = make_way(req, PTAG, (0b0001, 0), rvc_map=(0, 0))
            is_after = (flag ^ 0) ^ int(value > ftq)
            killed = not is_after
            pointer = ({"bpu_s2": (flag, value)} if value % 2 == 0
                       else {"bpu_s3": (flag, value)})
            observed = await agent.send(req, way0=way, mask_unread_banks=True,
                                        **pointer)
            if killed:
                assert observed is None, (
                    f"redirect({flag},{value}) must kill FTQ {ftq}")
            else:
                assert observed is not None, (
                    f"redirect({flag},{value}) must leave FTQ {ftq} alone")


@pytest.mark.feature("ICACHE-MAINPIPE-014")
async def test_satp_and_taken_flags_clear_on_the_next_fetch(mainpipe_agent):
    """The metadata registers must not keep the previous fetch's tag."""
    agent = mainpipe_agent
    first = make_fetch(0x9800, 3, has_satp_flush=1)
    second = make_fetch(0x9808, 15, taken=1)
    way_first = make_way(first, PTAG, (0b0001, 0), rvc_map=(0, 0))
    way_second = make_way(second, PTAG, (0b0010, 0), rvc_map=(0, 0))
    observed = await agent.send(first, second, way_first, way_second,
                                mask_unread_banks=True)
    assert observed.blocks[0].has_satp_flush == 1
    assert observed.blocks[1].taken_valid == 1

    third = make_fetch(0x9900, 15)
    way_third = make_way(third, PTAG, (0b0001, 0), rvc_map=(0, 0))
    observed = await agent.send(third, way0=way_third, mask_unread_banks=True)
    assert observed.blocks[0].has_satp_flush == 0


@pytest.mark.feature("ICACHE-MAINPIPE-014")
async def test_backend_exception_is_forwarded(mainpipe_agent):
    """A backend exception is both a flag and a code to the IFU."""
    agent = mainpipe_agent
    # The backend exception *code* is carried by the way-lookup entry (as the
    # ITLB exception field); the FTQ only adds the "has backend exception" tag.
    req = make_fetch(0x9A00, 15, has_backend_exception=1)
    way = make_way(req, PTAG, (0b0001, 0), rvc_map=(0, 0),
                   itlb_exception=model.EXC_AF)
    observed = await agent.send(req, way0=way, mask_unread_banks=True)
    assert observed.blocks[0].backend_exception == 1
    assert observed.blocks[0].exception == model.EXC_AF


@pytest.mark.feature("ICACHE-MAINPIPE-014")
async def test_first_fetch_taken_flag_is_forwarded(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x9B00, 7, taken=1)
    way = make_way(req, PTAG, (0b0001, 0), rvc_map=(0xFFFF_FFFF, 0))
    observed = await agent.send(req, way0=way, mask_unread_banks=True)
    assert observed.blocks[0].taken_valid == 1


@pytest.mark.feature("ICACHE-MAINPIPE-014")
async def test_taken_flag_clears_on_the_next_fetch(mainpipe_agent):
    """taken is a per-request tag: it must go back to 0 after a taken fetch."""
    agent = mainpipe_agent
    taken_req = make_fetch(0x9C00, 7, taken=1)
    way = make_way(taken_req, PTAG, (0b0001, 0), rvc_map=(0xFFFF_FFFF, 0))
    observed = await agent.send(taken_req, way0=way, mask_unread_banks=True)
    assert observed.blocks[0].taken_valid == 1

    plain = make_fetch(0x9C00, 15)
    way2 = make_way(plain, PTAG, (0b0001, 0), rvc_map=(0xFFFF_FFFF, 0))
    observed = await agent.send(plain, way0=way2, mask_unread_banks=True)
    assert observed.blocks[0].taken_valid == 0


@pytest.mark.feature("ICACHE-MAINPIPE-014")
async def test_backend_exception_tag_clears(mainpipe_agent):
    agent = mainpipe_agent
    flagged = make_fetch(0x9E00, 15, has_backend_exception=1)
    way = make_way(flagged, PTAG, (0b0001, 0), rvc_map=(0, 0),
                   itlb_exception=model.EXC_AF)
    first = await agent.send(flagged, way0=way, mask_unread_banks=True)
    assert first.blocks[0].backend_exception == 1

    plain = make_fetch(0x9E40, 15)
    way_plain = make_way(plain, PTAG, (0b0001, 0), rvc_map=(0, 0))
    second = await agent.send(plain, way0=way_plain, mask_unread_banks=True)
    assert second.blocks[0].backend_exception == 0


@pytest.mark.feature("ICACHE-MAINPIPE-003")
async def test_vs_non_leaf_tag_follows_the_lookup(mainpipe_agent):
    agent = mainpipe_agent
    marked = make_fetch(0x9E80, 15)
    way = make_way(marked, PTAG, (0b0001, 0), rvc_map=(0, 0),
                   itlb_exception=model.EXC_PF)
    way = dataclasses.replace(way, vs_non_leaf=1)
    first = await agent.send(marked, way0=way, mask_unread_banks=True)
    assert first.blocks[0].vs_non_leaf == 1

    plain = make_fetch(0x9EC0, 15)
    way_plain = make_way(plain, PTAG, (0b0001, 0), rvc_map=(0, 0))
    second = await agent.send(plain, way0=way_plain, mask_unread_banks=True)
    assert second.blocks[0].vs_non_leaf == 0


@pytest.mark.feature("ICACHE-MAINPIPE-010")
async def test_ecc_report_clears_on_the_next_clean_fetch(mainpipe_agent):
    """The BEU report is a one-cycle pulse, not a sticky flag."""
    agent = mainpipe_agent
    await agent.ecc_on()
    req = make_fetch(0x9F00, 15)
    # Odd-parity words with a zero stored code: an ECC error, not a TL error.
    way = make_way(req, PTAG, (0b0001, 0), rvc_map=(0, 0), words=(1,) * 8)
    first = await agent.send(req, way0=way)
    assert agent.last_corrupt[0] == 1
    assert agent.last_error_valid == 1

    clean = make_fetch(0x9F40, 15)
    # Even-parity words with a zero code: no ECC error.
    way_clean = make_way(clean, PTAG, (0b0001, 0), rvc_map=(0, 0),
                         words=(0,) * 8)
    second = await agent.send(clean, way0=way_clean)
    assert second.ifu_valid == 1
    assert agent.last_corrupt == (0, 0, 0, 0)
    assert agent.last_error_valid == 0
    await agent.ecc_off()


@pytest.mark.feature("ICACHE-MAINPIPE-001")
async def test_instruction_range_shrinks_from_two_to_one(mainpipe_agent):
    """The range mask's low bits must clear when the fetch shrinks.

    A one-instruction fetch (end=0) has range 0b1, so a preceding two-
    instruction fetch (end=1, range 0b11) drives bit 1 from 1 back to 0.
    """
    agent = mainpipe_agent
    two = make_fetch(0xA000, 1)
    way = make_way(two, PTAG, (0b0001, 0), rvc_map=(0xFFFF_FFFF, 0))
    await agent.send(two, way0=way, mask_unread_banks=True)
    one = make_fetch(0xA000, 0)
    way_one = make_way(one, PTAG, (0b0001, 0), rvc_map=(0xFFFF_FFFF, 0))
    observed = await agent.send(one, way0=way_one, mask_unread_banks=True)
    assert observed.total_range == 0b1
    assert observed.blocks[0].size == 1
