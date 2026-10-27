"""Functional points of ICacheMainPipe."""

from __future__ import annotations

import pytest

from icacheverify.mainpipe.case.definitions import data_word
from icacheverify.mainpipe.case.definitions import make_fetch
from icacheverify.mainpipe.case.definitions import make_way
from icacheverify.mainpipe.model import mainpipe as model

PTAG = 0x12345


@pytest.mark.feature("ICACHE-MAINPIPE-001")
async def test_hit_returns_data_and_touches_the_replacer(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x1000, 15, ftq_idx=3, taken=1)
    way = make_way(req, PTAG, (0b0001, 0))
    observed = await agent.send(req, way0=way)

    assert observed.ifu_valid == 1
    block = observed.blocks[0]
    assert block.valid == 1
    assert block.start_vaddr == 0x1000
    assert block.ftq_idx == 3
    assert block.taken_valid == 1
    assert block.data == data_word(req.vset[0], 0), "a hit must return the array data"
    assert block.exception == model.EXC_NONE
    assert block.cross_line == 0
    assert block.paddr == model.get_paddr(PTAG, 0x1000) & ((1 << 47) - 1)
    assert observed.touches == (model.Touch(0, 0, req.vset[0], 0),)


@pytest.mark.feature("ICACHE-MAINPIPE-002")
async def test_miss_requests_the_line_then_returns_refill_data(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x2000, 15)
    way = make_way(req, PTAG, (0, 0))
    refill = model.MissResponse(
        block=model.get_blk_addr(PTAG, 0x2000),
        vset=req.vset[0],
        data=data_word(req.vset[0], 2),
        waymask=0b0100,
    )
    observed = await agent.send(req, way0=way, refill=refill)
    assert observed.ifu_valid == 1
    assert observed.blocks[0].data == refill.data
    assert observed.blocks[0].exception == model.EXC_NONE


@pytest.mark.feature("ICACHE-MAINPIPE-002")
async def test_second_line_of_a_cross_line_fetch_is_requested(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x3020, 31)
    way = make_way(req, PTAG, (0b0001, 0))
    refill = model.MissResponse(
        block=model.get_blk_addr(PTAG, 0x3060),
        vset=req.vset[1],
        data=data_word(req.vset[1], 1),
        waymask=0b0010,
    )
    observed = await agent.send(req, way0=way, refill=refill)
    assert observed.ifu_valid == 1
    assert observed.blocks[0].cross_line == 1
    assert observed.blocks[0].data & ((1 << 256) - 1) == refill.data & ((1 << 256) - 1)


@pytest.mark.feature("ICACHE-MAINPIPE-003")
async def test_itlb_exception_suppresses_the_fetch(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x4000, 15)
    way = make_way(req, PTAG, (0, 0), itlb_exception=model.EXC_PF,
                   gpaddr=0xDEAD_BEE0)
    observed = await agent.send(req, way0=way)
    assert observed.ifu_valid == 1
    assert observed.blocks[0].exception == model.EXC_PF
    assert observed.blocks[0].gpaddr == 0xDEAD_BEE0


@pytest.mark.feature("ICACHE-MAINPIPE-004")
async def test_pmp_access_fault_is_reported(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x5000, 15)
    way = make_way(req, PTAG, (0, 0))
    observed = await agent.send(req, way0=way, pmp_instr=1)
    assert observed.blocks[0].exception == model.EXC_AF


@pytest.mark.feature("ICACHE-MAINPIPE-005")
async def test_mmio_is_not_fetched(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x6000, 15)
    way = make_way(req, PTAG, (0, 0))
    observed = await agent.send(req, way0=way, pmp_mmio=1)
    assert observed.ifu_valid == 1
    assert observed.blocks[0].pmp_mmio == 1
    assert observed.blocks[0].exception == model.EXC_NONE


@pytest.mark.feature("ICACHE-MAINPIPE-006")
async def test_corrupt_refill_raises_a_hardware_error(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x7000, 15)
    way = make_way(req, PTAG, (0, 0))
    refill = model.MissResponse(
        block=model.get_blk_addr(PTAG, 0x7000), vset=req.vset[0],
        data=data_word(req.vset[0], 1), corrupt=1, denied=0)
    observed = await agent.send(req, way0=way, refill=refill)
    assert observed.blocks[0].exception == model.EXC_HWE


@pytest.mark.feature("ICACHE-MAINPIPE-006")
async def test_denied_refill_raises_an_access_fault(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x7400, 15)
    way = make_way(req, PTAG, (0, 0))
    refill = model.MissResponse(
        block=model.get_blk_addr(PTAG, 0x7400), vset=req.vset[0],
        data=0, corrupt=1, denied=1)
    observed = await agent.send(req, way0=way, refill=refill)
    assert observed.blocks[0].exception == model.EXC_AF


@pytest.mark.feature("ICACHE-MAINPIPE-007")
async def test_two_fetches_are_reported_together(mainpipe_agent):
    agent = mainpipe_agent
    req0 = make_fetch(0x8000, 15, ftq_idx=1, vset=(0x10, 0x10))
    req1 = make_fetch(0x9000, 15, ftq_idx=2, vset=(0x20, 0x20))
    way0 = make_way(req0, PTAG, (0b0001, 0))
    way1 = make_way(req1, PTAG, (0b0010, 0))
    observed = await agent.send(req0, req1, way0, way1)
    assert observed.two_fetch_valid == 1
    assert observed.blocks[0].valid == 1 and observed.blocks[1].valid == 1
    assert observed.total_range == 0xFFFF_FFFF
    assert observed.touches == (model.Touch(0, 0, 0x10, 0),
                                model.Touch(1, 0, 0x20, 1))


@pytest.mark.feature("ICACHE-MAINPIPE-007")
async def test_second_fetch_is_dropped_on_a_data_bank_conflict(mainpipe_agent):
    agent = mainpipe_agent
    req0 = make_fetch(0x8000, 15, vset=(0x10, 0x10))
    req1 = make_fetch(0x9000, 15, vset=(0x20, 0x20))
    # Same way, different set, overlapping banks: the array cannot read both.
    way0 = make_way(req0, PTAG, (0b0001, 0))
    way1 = make_way(req1, PTAG, (0b0001, 0))
    observed = await agent.send(req0, req1, way0, way1)
    assert observed.two_fetch_valid == 0
    assert observed.blocks[1].valid == 0


@pytest.mark.feature("ICACHE-MAINPIPE-007")
async def test_second_fetch_is_dropped_when_the_first_is_mmio(mainpipe_agent):
    agent = mainpipe_agent
    req0 = make_fetch(0x8000, 15, vset=(0x10, 0x10))
    req1 = make_fetch(0x9000, 15, vset=(0x20, 0x20))
    way0 = make_way(req0, PTAG, (0b0001, 0), is_mmio=1)
    way1 = make_way(req1, PTAG, (0b0010, 0))
    observed = await agent.send(req0, req1, way0, way1)
    assert observed.two_fetch_valid == 0
    assert observed.blocks[1].valid == 0


@pytest.mark.feature("ICACHE-MAINPIPE-008")
async def test_flush_suppresses_the_in_flight_fetch(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0xA000, 15)
    way = make_way(req, PTAG, (0b0001, 0))
    absent = model.FetchRequest(0, 0, 0, 0, valid=0)
    empty_way = model.WayEntry(waymask=(0, 0), vset=(0, 0), valid=0)

    agent.flush_driver.set({"flush": 1})
    await agent._edge()
    await agent.pulse_request(req, absent, way, empty_way)
    for _ in range(6):
        assert agent.ifu_valid() == 0, "a flushed fetch must not reach the IFU"
        assert agent.miss_valid() == 0, "a flushed fetch must not request a refill"
        await agent._edge()
    agent.flush_driver.set({"flush": 0})
    await agent._edge()
    await agent._edge()

    # The pipe must recover and serve the next fetch normally.
    req2 = make_fetch(0xA100, 15)
    way2 = make_way(req2, PTAG, (0b0010, 0))
    observed = await agent.send(req2, way0=way2)
    assert observed.ifu_valid == 1
    assert observed.blocks[0].data == data_word(req2.vset[0], 1)


@pytest.mark.feature("ICACHE-MAINPIPE-009")
async def test_cross_line_rvc_map_is_stitched_and_aligned(mainpipe_agent):
    agent = mainpipe_agent
    req = make_fetch(0x2020, 20, taken=1)
    way = make_way(req, PTAG, (0b0001, 0b0010),
                   rvc_map=(0x00FF00FF, 0x00FF00FF))
    observed = await agent.send(req, way0=way)
    block = observed.blocks[0]
    # Slots 16..31 come from line 0 (0x00FF00FF >> 16 = 0x00FF), slots 0..4 of
    # line 1 land on combined slots 16..20 ((0x00FF00FF << 16) & 0x1F0000).
    assert observed.maybe_rvc_map == 0x001F_00FF
    assert observed.first_range == 0x001F_FFFF
    assert observed.total_range == 0x001F_FFFF
    assert block.taken_bits == 20 and block.size == 21
    assert block.cross_line == 1


@pytest.mark.feature("ICACHE-MAINPIPE-010")
async def test_ecc_error_sets_corrupt_and_reports_to_beu(mainpipe_agent):
    agent = mainpipe_agent
    await agent.ecc_on()
    req = make_fetch(0xB000, 15)
    way = make_way(req, PTAG, (0b0001, 0), rvc_map=(0, 0))
    observed = await agent.send(req, way0=way)
    assert observed.ifu_valid == 1
    # The data-array peer returns a non-zero word with a zero ECC code, so the
    # parity check must flag the request/port.
    assert agent.last_corrupt[0] == 1
    assert agent.last_error_valid == 1


@pytest.mark.feature("ICACHE-MAINPIPE-011")
async def test_second_fetch_can_cross_lines_and_miss(mainpipe_agent):
    """Request 1 has its own cross-line second line, miss tracking and refill."""
    agent = mainpipe_agent
    req0 = make_fetch(0xC800, 15, vset=(0x90, 0x90))
    req1 = make_fetch(0xC020, 31, vset=(0xA0, 0xA1))
    way0 = make_way(req0, PTAG, (0b0001, 0))
    way1 = make_way(req1, PTAG, (0, 0))
    refills = [
        model.MissResponse(
            block=model.get_blk_addr(PTAG, 0xC020), vset=0xA0,
            data=data_word(0xA0, 1), maybe_rvc_map=0xFFFF_0000),
        model.MissResponse(
            block=model.get_blk_addr(PTAG, 0xC060), vset=0xA1,
            data=data_word(0xA1, 2), maybe_rvc_map=0x0F0F_0F0F),
    ]
    observed = await agent.send(req0, req1, way0, way1, refill=refills)
    assert observed.two_fetch_valid == 1
    assert observed.blocks[0].valid == 1 and observed.blocks[1].valid == 1
    # req1's cross-line flag is not an output of the DUT; its two refilled
    # lines are visible through the assembled data instead.
    assert observed.blocks[1].data & ((1 << 256) - 1) == (
        data_word(0xA1, 2) & ((1 << 256) - 1))
    assert observed.blocks[1].data >> 256 == data_word(0xA0, 1) >> 256


@pytest.mark.feature("ICACHE-MAINPIPE-011")
async def test_second_fetch_refill_exception_is_reported(mainpipe_agent):
    agent = mainpipe_agent
    req0 = make_fetch(0xD000, 15, vset=(0xB0, 0xB0))
    req1 = make_fetch(0xD800, 15, vset=(0xB8, 0xB8))
    way0 = make_way(req0, PTAG, (0b0001, 0))
    way1 = make_way(req1, PTAG, (0, 0))
    refill = model.MissResponse(
        block=model.get_blk_addr(PTAG, 0xD800), vset=0xB8,
        data=data_word(0xB8, 1), corrupt=1, denied=0)
    observed = await agent.send(req0, req1, way0, way1, refill=refill)
    assert observed.blocks[0].exception == model.EXC_NONE
    assert observed.blocks[1].exception == model.EXC_HWE


@pytest.mark.feature("ICACHE-MAINPIPE-012")
async def test_ecc_checks_every_data_bank_of_a_full_line_fetch(mainpipe_agent):
    """A full-line fetch selects all eight data banks of request 0."""
    agent = mainpipe_agent
    await agent.ecc_on()
    req0 = make_fetch(0xE000, 31, vset=(0xC0, 0xC0))
    way0 = make_way(req0, PTAG, (0b0001, 0), rvc_map=(0, 0))
    await agent.send(req0, way0=way0)
    assert agent.last_corrupt[0] == 1
    assert agent.last_error_valid == 1


@pytest.mark.feature("ICACHE-MAINPIPE-012")
async def test_ecc_checks_the_second_fetch_banks(mainpipe_agent):
    """A cross-line second fetch selects its banks from both of its lines."""
    agent = mainpipe_agent
    await agent.ecc_on()
    req0 = make_fetch(0xE800, 3, vset=(0xC8, 0xC8))
    req1 = make_fetch(0xF020, 31, vset=(0xD0, 0xD1))
    way0 = make_way(req0, PTAG, (0b0001, 0), rvc_map=(0, 0))
    way1 = make_way(req1, PTAG, (0b0010, 0b0010), rvc_map=(0, 0))
    observed = await agent.send(req0, req1, way0, way1)
    assert observed.two_fetch_valid == 1
    assert agent.last_corrupt[2] == 1, "request 1 must flag its corrupt banks"
    assert agent.last_error_valid == 1


@pytest.mark.feature("ICACHE-MAINPIPE-012")
async def test_ecc_flags_every_bank_of_a_second_fetch_full_line(mainpipe_agent):
    """Every data bank of request 1 must be checked, not only the low banks.

    Each bank's word is given odd parity while its stored code is zero, so every
    selected bank of request 1 must raise its corrupt bit.  Banks 1, 5 and 6 are
    only reached when request 1 fetches a full line, which the earlier cases did
    not combine with a parity mismatch.
    """
    agent = mainpipe_agent
    await agent.ecc_on()
    req0 = make_fetch(0xE800, 3, vset=(0xC8, 0xC8))
    req1 = make_fetch(0xF000, 31, vset=(0xD8, 0xD9))
    way0 = make_way(req0, PTAG, (0b0001, 0), rvc_map=(0, 0))
    way1 = make_way(req1, PTAG, (0b0010, 0), rvc_map=(0, 0),
                    words=(1,) * 8)
    observed = await agent.send(req0, req1, way0, way1)
    assert observed.two_fetch_valid == 1
    # Request 1 is a full-line fetch, so only its first line slot carries
    # selected banks; all eight of them must be checked.
    assert agent.last_corrupt[2] == 1
    assert agent.last_corrupt[3] == 0
    assert agent.last_error_valid == 1


@pytest.mark.feature("ICACHE-MAINPIPE-006")
async def test_denied_second_line_refill_reports_access_fault(mainpipe_agent):
    """A denied refill of the second line must be seen by the second line slot."""
    agent = mainpipe_agent
    req = make_fetch(0x7620, 31, vset=(0xB0, 0xB1))
    way = make_way(req, PTAG, (0, 0), rvc_map=(0, 0))
    line0 = model.MissResponse(
        block=model.get_blk_addr(PTAG, req.vaddr & ~0x3F),
        vset=req.vset[0], data=data_word(req.vset[0], 0))
    line1 = model.MissResponse(
        block=model.get_blk_addr(PTAG, (req.vaddr & ~0x3F) + 0x40),
        vset=req.vset[1], data=0, corrupt=1, denied=1)
    observed = await agent.send(req, way0=way, refill=[line0, line1])
    assert observed.blocks[0].exception == model.EXC_AF


@pytest.mark.feature("ICACHE-MAINPIPE-007")
async def test_both_fetches_report_corruption(mainpipe_agent):
    """When both fetches return corrupt data, both corrupt slots must be set.

    The first corrupt-port mux only chooses between two non-empty ports; a
    single corrupt fetch leaves that arm untested.
    """
    agent = mainpipe_agent
    req0 = make_fetch(0x7800, 3, ftq_idx=1, vset=(0xC0, 0xC0))
    req1 = make_fetch(0x7C08, 11, ftq_idx=2, vset=(0xD0, 0xD0))
    way0 = make_way(req0, PTAG, (0, 0), rvc_map=(0, 0))
    way1 = make_way(req1, PTAG, (0, 0), rvc_map=(0, 0))
    refill0 = model.MissResponse(
        block=model.get_blk_addr(PTAG, req0.vaddr), vset=req0.vset[0],
        data=0, corrupt=1, denied=0)
    refill1 = model.MissResponse(
        block=model.get_blk_addr(PTAG, req1.vaddr), vset=req1.vset[0],
        data=0, corrupt=1, denied=0)
    observed = await agent.send(req0, req1, way0, way1,
                                refill=[refill0, refill1])
    assert observed.two_fetch_valid == 1
    assert observed.blocks[0].exception == model.EXC_HWE
    assert observed.blocks[1].exception == model.EXC_HWE


@pytest.mark.feature("ICACHE-MAINPIPE-006")
async def test_corrupt_second_line_of_the_first_fetch_is_the_reported_port(mainpipe_agent):
    """A cross-line fetch whose *second* line is corrupt reports that line.

    The first corrupt-port mux has a distinct arm for "request 0's second line"
    that is only reached when request 0's first line is clean.
    """
    agent = mainpipe_agent
    req = make_fetch(0x7A20, 31, vset=(0xE0, 0xE1))
    way = make_way(req, PTAG, (0, 0), rvc_map=(0, 0))
    line0 = model.MissResponse(
        block=model.get_blk_addr(PTAG, req.vaddr & ~0x3F),
        vset=req.vset[0], data=data_word(req.vset[0], 0))
    line1 = model.MissResponse(
        block=model.get_blk_addr(PTAG, (req.vaddr & ~0x3F) + 0x40),
        vset=req.vset[1], data=0, corrupt=1, denied=0)
    observed = await agent.send(req, way0=way, refill=[line0, line1])
    assert observed.blocks[0].exception == model.EXC_HWE


@pytest.mark.feature("ICACHE-MAINPIPE-011")
async def test_denied_refill_of_the_second_fetch_reports_access_fault(mainpipe_agent):
    """Request 1's TileLink exception has its own register and mux arm."""
    agent = mainpipe_agent
    req0 = make_fetch(0x8000, 15, ftq_idx=1, vset=(0x10, 0x10))
    req1 = make_fetch(0x8040, 15, ftq_idx=2, vset=(0x20, 0x20))
    way0 = make_way(req0, PTAG, (0b0001, 0), rvc_map=(0, 0))
    way1 = make_way(req1, PTAG, (0, 0), rvc_map=(0, 0))
    refill = model.MissResponse(
        block=model.get_blk_addr(PTAG, req1.vaddr), vset=req1.vset[0],
        data=0, corrupt=1, denied=1)
    observed = await agent.send(req0, req1, way0, way1, refill=refill)
    assert observed.two_fetch_valid == 1
    assert observed.blocks[1].exception == model.EXC_AF


@pytest.mark.feature("ICACHE-MAINPIPE-009")
async def test_second_fetch_refill_map_is_shifted_by_the_gap(mainpipe_agent):
    """Request 1 starts after request 0's block, so its map shifts right."""
    agent = mainpipe_agent
    req0 = make_fetch(0x8200, 3, ftq_idx=1, vset=(0x30, 0x30))
    req1 = make_fetch(0x820C, 15, ftq_idx=2, vset=(0x40, 0x40))
    way0 = make_way(req0, PTAG, (0b0001, 0), rvc_map=(0, 0))
    way1 = make_way(req1, PTAG, (0, 0), rvc_map=(0, 0))
    refill = model.MissResponse(
        block=model.get_blk_addr(PTAG, req1.vaddr), vset=req1.vset[0],
        data=data_word(req1.vset[0], 0), maybe_rvc_map=0xFFFF_FFFF)
    expected = model.predict(req0, req1, way0, way1, miss=refill)
    observed = await agent.send(req0, req1, way0, way1, refill=refill,
                                check=False)
    # Banks outside the fetch's bank mask return stale storage; only the
    # aligned instruction map is architecturally defined here.
    assert observed.two_fetch_valid == 1
    assert observed.blocks[1].valid == 1
    assert observed.maybe_rvc_map == expected.maybe_rvc_map
    assert observed.first_range == expected.first_range
    assert observed.total_range == expected.total_range


@pytest.mark.feature("ICACHE-MAINPIPE-010")
async def test_second_line_meta_corruption_is_the_reported_port(mainpipe_agent):
    """Only request 0's second line is corrupt: the inner corrupt-port arm runs.

    The first corrupt-port mux has an arm for "request 0's second line", reached
    only when the first line is clean.  ECC is enabled and the second line's
    stored parity does not match its tag/RVC map, while the first line matches
    and all data words have even parity.
    """
    agent = mainpipe_agent
    await agent.ecc_on()
    req = make_fetch(0x8820, 31, vset=(0x50, 0x51))
    rvc0, rvc1 = 0xFFFF_FFFF, 0x0000_0000
    parity = lambda tag, rvc: (tag.bit_count() ^ rvc.bit_count()) & 1
    way = make_way(req, PTAG, (0b0001, 0b0001),
                   rvc_map=(rvc0, rvc1),
                   words=(0,) * 8)
    # make_way does not take meta_codes; rebuild the entry with the codes.
    import dataclasses
    way = dataclasses.replace(
        way, meta_codes=(parity(PTAG, rvc0), parity(PTAG, rvc1) ^ 1))
    observed = await agent.send(req, way0=way)
    assert observed.blocks[0].valid == 1
    assert agent.last_corrupt[0] == 0, "the first line must be clean"
    assert agent.last_corrupt[1] == 1, "the second line must flag corruption"
    assert agent.last_error_valid == 1


@pytest.mark.feature("ICACHE-MAINPIPE-015")
async def test_miss_bubble_is_asserted_while_the_miss_port_blocks(mainpipe_agent):
    """``perf.pendingMiss`` marks the fetch that is waiting to issue its miss.

    The signal is ``s1_valid && !s1_fetchFinish``: it is high for every cycle
    the accepted fetch still has to send a miss request, and it drops on the
    cycle the miss unit takes it.  It is a topdown performance hint, so its
    exact cycle semantics matter only in this unambiguous blocked scenario;
    the agent asserts the level on every held cycle and after acceptance.
    """
    agent = mainpipe_agent
    req = make_fetch(0xA100, 15)
    way = make_way(req, PTAG, (0, 0), rvc_map=(0, 0))
    refill = model.MissResponse(
        block=model.get_blk_addr(PTAG, req.vaddr), vset=req.vset[0],
        data=data_word(req.vset[0], 0), maybe_rvc_map=0xFFFF_FFFF)
    observed = await agent.send(req, way0=way, refill=refill,
                                miss_stall_cycles=5, mask_unread_banks=True)
    assert observed.ifu_valid == 1
