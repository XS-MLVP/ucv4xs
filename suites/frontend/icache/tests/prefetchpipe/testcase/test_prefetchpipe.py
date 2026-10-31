"""Functional points of ICachePrefetchPipe."""

from __future__ import annotations

import pytest

from suites.frontend.icache.prefetchpipe.model import prefetchpipe as model
from suites.frontend.icache.prefetchpipe.model.prefetchpipe import ItlbResponse
from suites.frontend.icache.prefetchpipe.model.prefetchpipe import MetaEntry
from suites.frontend.icache.prefetchpipe.model.prefetchpipe import PrefetchRequest

PTAG = 0x23456


def make_prefetch(vaddr: int, end_position: int, ftq_idx: int = 0, *,
                  soft: int = 0, backend: int = 0) -> PrefetchRequest:
    return PrefetchRequest(
        vaddr=vaddr,
        next_vaddr=vaddr + 64,
        end_position=end_position,
        ftq_idx=ftq_idx,
        is_cross_line=model.is_cross_line(vaddr, end_position),
        is_soft_prefetch=soft,
        backend_exception=backend,
        vset=(model.get_idx(vaddr), model.get_idx(vaddr + 64)),
    )


def hit_meta(way: int, ptag: int = PTAG, rvc: int = 0xFFFF_FFFF,
             code: int = 0) -> tuple[tuple[MetaEntry, ...], tuple[MetaEntry, ...]]:
    entries = tuple(
        MetaEntry(ptag=ptag if index == way else 0x1111 + index,
                  rvc=rvc if index == way else 0,
                  code=code if index == way else 0)
        for index in range(model.WAYS))
    return (entries, entries)


def miss_meta() -> tuple[tuple[MetaEntry, ...], tuple[MetaEntry, ...]]:
    entries = tuple(MetaEntry(ptag=0x1111 + index) for index in range(model.WAYS))
    return (entries, entries)


def itlb_hit(paddr: int = PTAG << 12, pbmt: int = 0, **kwargs) -> ItlbResponse:
    return ItlbResponse(miss=0, paddr=paddr, pbmt=pbmt, **kwargs)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-001")
async def test_meta_hit_writes_the_way_lookup_entry(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req = make_prefetch(0x1000, 31, ftq_idx=5)
    observed = await agent.send(req, itlb=itlb_hit(),
                                meta=hit_meta(1, rvc=0x1234_5678, code=1))
    write = observed.writes[0]
    assert write.valid == 1
    assert write.ftq_idx == 5
    assert write.vset == (model.get_idx(0x1000), model.get_idx(0x1060))
    # Line 1 is not read for a single-line prefetch, so its map is empty.
    assert write.waymask == (0b0010, 0)
    assert write.ptag == PTAG
    assert write.rvc == (0x1234_5678, 0)
    assert write.code == (1, 0)
    assert observed.writes[1].valid == 0
    assert observed.misses == ()


@pytest.mark.feature("ICACHE-PREFETCHPIPE-002")
async def test_meta_miss_requests_the_line(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req = make_prefetch(0x2000, 31)
    observed = await agent.send(req, itlb=itlb_hit(), meta=miss_meta())
    assert observed.misses == (
        (model.get_blk_addr(PTAG, 0x2000), model.get_idx(0x2000)),)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-002")
async def test_cross_line_prefetch_reads_and_requests_both_lines(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req = make_prefetch(0x3020, 31)
    observed = await agent.send(req, itlb=itlb_hit(), meta=miss_meta())
    assert observed.meta_double == 1
    assert observed.meta_sets == (model.get_idx(0x3020), model.get_idx(0x3060))
    assert observed.misses == (
        (model.get_blk_addr(PTAG, 0x3020), model.get_idx(0x3020)),
        (model.get_blk_addr(PTAG, 0x3060), model.get_idx(0x3060)),
    )


@pytest.mark.feature("ICACHE-PREFETCHPIPE-003")
async def test_itlb_miss_stalls_and_resends_the_translation(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req = make_prefetch(0x4000, 31)
    meta = hit_meta(0)
    agent.drive_itlb(ItlbResponse(miss=1))
    agent.drive_meta(meta)
    await agent._edge()
    expected = model.predict(req, PrefetchRequest(0, 0, 0, 0),
                             itlb=itlb_hit(), meta=meta)
    await agent.pulse_request(req, PrefetchRequest(0, 0, 0, 0), model.CASE_CONFLICT)
    for _ in range(3):
        assert agent.way_valid(0) == 0, "no way lookup write during an ITLB miss"
        assert agent.pending_itlb_miss() == 1
        await agent._edge()
    agent.drive_itlb(itlb_hit())
    observed = await agent.wait_result(expected)
    assert observed.writes[0].waymask == (0b0001, 0)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-004")
async def test_meta_read_is_resent_after_the_itlb_miss(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req = make_prefetch(0x4800, 31)
    meta = hit_meta(2)
    agent.drive_itlb(ItlbResponse(miss=1))
    agent.drive_meta(meta)
    await agent._edge()
    expected = model.predict(req, PrefetchRequest(0, 0, 0, 0),
                             itlb=itlb_hit(), meta=meta)
    await agent.pulse_request(req, PrefetchRequest(0, 0, 0, 0), model.CASE_CONFLICT)
    agent.meta_ready_driver.set({"ready": 0})
    for _ in range(3):
        await agent._edge()
    agent.drive_itlb(itlb_hit())
    for _ in range(8):
        if agent.meta_req_valid():
            break
        await agent._edge()
    assert agent.meta_req_valid() == 1, "the meta read must be re-issued"
    agent.meta_ready_driver.set({"ready": 1})
    observed = await agent.wait_result(expected)
    assert observed.writes[0].waymask == (0b0100, 0)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-005")
async def test_prefetch_disabled_still_writes_but_requests_nothing(prefetchpipe_agent):
    agent = prefetchpipe_agent
    agent.csr_driver.set({"enable": 0})
    agent.pf_enable = 0
    await agent._edge()
    req = make_prefetch(0x5000, 31)
    observed = await agent.send(req, itlb=itlb_hit(), meta=miss_meta())
    assert observed.writes[0].valid == 1
    assert observed.misses == (), "csrPfEnable must gate the miss request"


@pytest.mark.feature("ICACHE-PREFETCHPIPE-006")
async def test_soft_prefetch_is_not_written_to_the_way_lookup(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req = make_prefetch(0x6000, 31, soft=1)
    observed = await agent.send(req, itlb=itlb_hit(), meta=hit_meta(0))
    assert observed.writes[0].valid == 0
    assert observed.writes[1].valid == 0
    assert observed.misses == ()


@pytest.mark.feature("ICACHE-PREFETCHPIPE-007")
async def test_itlb_exception_is_carried_and_suppresses_the_miss(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req = make_prefetch(0x7000, 31)
    observed = await agent.send(req, itlb=itlb_hit(pf=1, gpaddr=0xDEAD_B000),
                                meta=miss_meta())
    write = observed.writes[0]
    assert write.exception == model.EXC_PF
    assert write.gpaddr == 0xDEAD_B000
    assert observed.misses == ()


@pytest.mark.feature("ICACHE-PREFETCHPIPE-007")
async def test_mmio_suppresses_the_miss_and_sets_the_flag(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req = make_prefetch(0x7400, 31)
    observed = await agent.send(req, itlb=itlb_hit(pbmt=2), meta=miss_meta())
    assert observed.writes[0].is_mmio == 1
    assert observed.writes[0].itlb_pbmt == 2
    assert observed.misses == ()


@pytest.mark.feature("ICACHE-PREFETCHPIPE-008")
async def test_flush_flushes_the_itlb_pipe_and_blocks_the_write(prefetchpipe_agent):
    agent = prefetchpipe_agent
    agent.flush_driver.set({"flush": 1})
    await agent._edge()
    assert agent.itlb_flush_pipe() == 1
    await agent._edge()
    assert agent.itlb_flush_pipe() == 1
    agent.flush_driver.set({"flush": 0})
    await agent._edge()
    await agent._edge()
    # A prefetch after the flush must still work.
    req = make_prefetch(0x8000, 31)
    observed = await agent.send(req, itlb=itlb_hit(), meta=hit_meta(3))
    assert observed.writes[0].valid == 1
    assert observed.writes[0].waymask == (0b1000, 0)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-009")
async def test_two_prefetch_case_interleaves_the_meta_reads(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req0 = make_prefetch(0x9000, 15, ftq_idx=1)
    req1 = make_prefetch(0x9100, 15, ftq_idx=2)
    meta = hit_meta(0)
    observed = await agent.send(req0, req1, case=model.CASE_INTERLEAVE,
                                itlb=itlb_hit(), meta=meta)
    assert observed.writes[0].valid == 1
    assert observed.writes[1].valid == 1
    assert observed.meta_sets == (model.get_idx(0x9000), model.get_idx(0x9100))
    assert observed.writes[1].ftq_idx == 2
    assert observed.writes[1].vset == (model.get_idx(0x9100),
                                       model.get_idx(0x9160))


@pytest.mark.feature("ICACHE-PREFETCHPIPE-009")
async def test_same_line_two_prefetch_reads_a_double_line(prefetchpipe_agent):
    agent = prefetchpipe_agent
    # Both blocks are in 0xA000..0xA03F; the first starts at +0x20 so it
    # crosses into the next line and the same-line case must read two lines.
    req0 = make_prefetch(0xA020, 31, ftq_idx=1)
    req1 = make_prefetch(0xA000, 7, ftq_idx=2)
    meta = (miss_meta()[0], hit_meta(1)[1])
    observed = await agent.send(req0, req1, case=model.CASE_SAME_LINE,
                                itlb=itlb_hit(), meta=meta)
    assert observed.meta_double == 1
    assert observed.writes[0].valid == 1 and observed.writes[1].valid == 1
    assert observed.writes[1].waymask == (0, 0b0010)
    assert observed.misses == (
        (model.get_blk_addr(PTAG, 0xA020), model.get_idx(0xA020)),)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-010")
async def test_refill_during_stage1_updates_the_metadata(prefetchpipe_agent):
    """A missUnit response seen in stage 1 must update the waymask that is written."""
    agent = prefetchpipe_agent
    req = make_prefetch(0x1100, 31)
    meta = miss_meta()
    agent.drive_itlb(itlb_hit())
    agent.drive_meta(meta)
    agent.miss_driver.set({
        "valid": 1,
        "blkPAddr": model.get_blk_addr(PTAG, 0x1100),
        "vSetIdx": model.get_idx(0x1100),
        "waymask": 0b0100,
        "maybeRvcMap": 0xFFFF_0000,
        "corrupt": 0,
    })
    await agent._edge()
    await agent.pulse_request(req, PrefetchRequest(0, 0, 0, 0), model.CASE_CONFLICT)
    await agent._edge()
    await agent._edge()
    agent.miss_driver.set({
        "valid": 0, "blkPAddr": 0, "vSetIdx": 0, "waymask": 0,
        "maybeRvcMap": 0, "corrupt": 0,
    })
    observed = await agent.wait_result(model.predict(req, PrefetchRequest(0, 0, 0, 0),
                                                     itlb=itlb_hit(), meta=meta),
                                      check=False)
    assert observed.writes[0].valid == 1
    assert observed.writes[0].waymask == (0b0100, 0)
    assert observed.writes[0].rvc == (0xFFFF_0000, 0)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-011")
async def test_miss_backpressure_holds_the_request_until_the_miss_is_accepted(prefetchpipe_agent):
    """A full miss unit must not lose the prefetch; it waits in the request stage."""
    agent = prefetchpipe_agent
    agent.miss_ready_driver.set({"ready": 0})
    await agent._edge()
    req = make_prefetch(0x1200, 31)
    meta = miss_meta()
    agent.drive_itlb(itlb_hit())
    agent.drive_meta(meta)
    await agent._edge()
    expected = model.predict(req, PrefetchRequest(0, 0, 0, 0),
                             itlb=itlb_hit(), meta=meta)
    await agent.pulse_request(req, PrefetchRequest(0, 0, 0, 0), model.CASE_CONFLICT)
    writes = None
    for _ in range(8):
        if agent.way_valid(0):
            writes = (agent.sample_write(0), agent.sample_write(1))
        await agent._edge()
        if writes is not None:
            break
    assert writes is not None, "the way lookup is written before the miss stage"
    # The request stage must keep offering the miss while the unit is full.
    for _ in range(4):
        assert agent.miss_valid() == 1, (
            "the request must be offered to the full miss unit and wait")
        await agent._edge()
    agent.miss_ready_driver.set({"ready": 1})
    observed = await agent.wait_result(expected, writes=writes)
    assert observed.misses == (
        (model.get_blk_addr(PTAG, 0x1200), model.get_idx(0x1200)),)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-010")
async def test_refill_with_a_different_tag_clears_the_stale_way(prefetchpipe_agent):
    """A refill that overwrote the same way in a different page clears the hit."""
    agent = prefetchpipe_agent
    req = make_prefetch(0x2020, 31)
    way0 = tuple(MetaEntry(ptag=PTAG if index == 1 else 0x3000 + index,
                           rvc=0xAAAA_0001, code=0) for index in range(model.WAYS))
    way1 = tuple(MetaEntry(ptag=PTAG if index == 2 else 0x4000 + index,
                           rvc=0xBBBB_0002, code=0) for index in range(model.WAYS))
    meta = (way0, way1)
    agent.drive_itlb(itlb_hit())
    agent.drive_meta(meta)
    other = model.get_blk_addr(PTAG + 1, 0x2020)
    agent.miss_driver.set({
        "valid": 1, "blkPAddr": other,
        "vSetIdx": model.get_idx(0x2020),
        "waymask": 0b0010, "maybeRvcMap": 0x1111, "corrupt": 0,
    })
    await agent._edge()
    await agent.pulse_request(req, PrefetchRequest(0, 0, 0, 0), model.CASE_CONFLICT)
    agent.miss_driver.set({
        "valid": 1,
        "blkPAddr": model.get_blk_addr(PTAG + 1, 0x2060),
        "vSetIdx": model.get_idx(0x2060),
        "waymask": 0b0100, "maybeRvcMap": 0x2222, "corrupt": 0,
    })
    await agent._edge()
    await agent._edge()
    agent.miss_driver.set({
        "valid": 0, "blkPAddr": 0, "vSetIdx": 0, "waymask": 0,
        "maybeRvcMap": 0, "corrupt": 0,
    })
    observed = await agent.wait_result(
        model.predict(req, PrefetchRequest(0, 0, 0, 0), itlb=itlb_hit(), meta=meta),
        check=False)
    assert observed.writes[0].valid == 1
    assert observed.writes[0].waymask == (0, 0), (
        "a same-way refill of another page must invalidate the stale hit")


@pytest.mark.feature("ICACHE-PREFETCHPIPE-010")
async def test_metadata_parity_code_is_carried_into_the_way_lookup(prefetchpipe_agent):
    """The stored ECC code of the hit way travels with the way-lookup entry.

    The metadata array stores a parity bit per way; the prefetch pipe must pass
    the selected way's code downstream unchanged, so the main pipe can check it.
    """
    agent = prefetchpipe_agent
    for code in (1, 0):
        # A cross-line request selects both metadata read ports, so both ports'
        # stored parity codes must travel into the two entry slots.
        req = make_prefetch(0x2420 + 0x40 * code, 31)
        meta = hit_meta(0, code=code)
        observed = await agent.send(req, itlb=itlb_hit(), meta=meta)
        assert observed.writes[0].valid == 1
        assert observed.writes[0].code == (code, code), (
            f"the way-lookup entry must carry metadata code {code} for both lines")


@pytest.mark.feature("ICACHE-PREFETCHPIPE-011")
async def test_second_request_waits_out_a_blocked_miss_stage(prefetchpipe_agent):
    """A second request occupies the request stage while stage 2 is blocked.

    With the miss unit full, the first request sits in stage 2.  The second
    request still writes its way-lookup entry, then must wait in the enter-stage
    2 state; once the first miss is accepted it is released and issues its own
    miss, so neither request is lost.
    """
    agent = prefetchpipe_agent
    agent.miss_ready_driver.set({"ready": 0})
    await agent._edge()
    itlb = itlb_hit()
    meta = miss_meta()
    agent.drive_itlb(itlb)
    agent.drive_meta(meta)
    agent.pmp_driver.set({"instr": 0, "mmio": 0})
    await agent._edge()

    req_a = make_prefetch(0x1200, 15)
    req_b = make_prefetch(0x1400, 15)
    absent = PrefetchRequest(0, 0, 0, 0)
    await agent.pulse_request(req_a, absent, model.CASE_CONFLICT)
    wrote_a = False
    for _ in range(12):
        if agent.way_valid(0):
            wrote_a = True
        await agent._edge()
        if wrote_a:
            break
    assert wrote_a, "the first request must write before entering stage 2"
    assert agent.miss_valid() == 1, "the first miss must wait for the full unit"

    # The second request is accepted while stage 2 is still blocked: its
    # way-lookup write happens, but it cannot enter stage 2 yet.
    await agent.pulse_request(req_b, absent, model.CASE_CONFLICT)
    wrote_b = False
    seen = []
    for _ in range(12):
        if not wrote_b and agent.way_valid(0):
            wrote_b = True
        if agent.miss_valid():
            seen.append(agent._value(agent.ports.miss_req, "blkPAddr"))
        await agent._edge()
        if wrote_b:
            break
    assert wrote_b, "the second request must write its way-lookup entry"

    agent.miss_ready_driver.set({"ready": 1})
    expected_blocks = {
        model.get_blk_addr(PTAG, 0x1200),
        model.get_blk_addr(PTAG, 0x1400),
    }
    observed_blocks = set(seen)
    for _ in range(40):
        if agent.miss_valid():
            observed_blocks.add(agent._value(agent.ports.miss_req, "blkPAddr"))
        await agent._edge()
        if observed_blocks >= expected_blocks:
            break
    assert observed_blocks >= expected_blocks, (
        f"both blocked requests must eventually miss, saw {observed_blocks}")


@pytest.mark.feature("ICACHE-PREFETCHPIPE-009")
async def test_overlap2_reads_the_two_lines_of_the_younger_request(prefetchpipe_agent):
    """fb1 lies in fb2's next line: both metadata ports serve fb2's lines.

    The first fetch block has no second line and must take its metadata from
    the second read port; the younger cross-line block owns both ports.
    """
    agent = prefetchpipe_agent
    req0 = make_prefetch(0x9040, 15, ftq_idx=1)
    req1 = make_prefetch(0x9000, 31, ftq_idx=2)
    meta = hit_meta(0)
    observed = await agent.send(req0, req1, case=model.CASE_OVERLAP2,
                                itlb=itlb_hit(), meta=meta)
    assert observed.meta_sets == (model.get_idx(0x9000), model.get_idx(0x9060))
    assert observed.writes[0].valid == 1 and observed.writes[1].valid == 1
    assert observed.writes[0].waymask == (0b0001, 0), (
        "fb1 must take its only line from the second read port")
    assert observed.writes[1].waymask == (0b0001, 0b0001), (
        "fb2 owns both read ports and both lines")


@pytest.mark.feature("ICACHE-PREFETCHPIPE-007")
async def test_itlb_gpf_and_af_exceptions(prefetchpipe_agent):
    """The GPF and AF translation faults are carried and suppress the miss."""
    agent = prefetchpipe_agent
    for index, (kwargs, expected) in enumerate(((dict(gpf=1), model.EXC_GPF),
                                                (dict(af=1), model.EXC_AF))):
        req = make_prefetch(0x2000 + 0x40 * index, 15)
        observed = await agent.send(req, itlb=itlb_hit(**kwargs),
                                    meta=miss_meta())
        assert observed.writes[0].exception == expected, (
            f"case {kwargs}: expected {expected}, got "
            f"{observed.writes[0].exception}")
        assert observed.misses == ()


@pytest.mark.feature("ICACHE-PREFETCHPIPE-007")
async def test_backend_exception_is_carried(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req = make_prefetch(0x2200, 15, backend=model.EXC_AF)
    observed = await agent.send(req, itlb=itlb_hit(), meta=miss_meta())
    assert observed.writes[0].exception == model.EXC_AF
    assert observed.misses == ()


@pytest.mark.feature("ICACHE-PREFETCHPIPE-007")
async def test_pmp_suppresses_the_miss_without_entering_the_entry(prefetchpipe_agent):
    """PMP is checked in stage 2; the speculative entry carries only translation.

    The RTL writes ``s1_itlbException_value`` into the way-lookup entry, while
    ``pmp_resp_instr`` is consumed when the miss request is formed.
    """
    agent = prefetchpipe_agent
    req = make_prefetch(0x2300, 15)
    observed = await agent.send(req, itlb=itlb_hit(), meta=miss_meta(),
                                pmp_instr=1)
    assert observed.writes[0].exception == model.EXC_NONE
    assert observed.misses == ()


@pytest.mark.feature("ICACHE-PREFETCHPIPE-010")
async def test_refill_updates_the_second_line_metadata_in_stage1(prefetchpipe_agent):
    """A cross-line request has a second metadata slot that a refill can correct."""
    agent = prefetchpipe_agent
    req = make_prefetch(0x1120, 31)
    meta = miss_meta()
    agent.drive_itlb(itlb_hit())
    agent.drive_meta(meta)
    agent.miss_driver.set({
        "valid": 1,
        "blkPAddr": model.get_blk_addr(PTAG, 0x1140),
        "vSetIdx": model.get_idx(0x1140),
        "waymask": 0b0010,
        "maybeRvcMap": 0x0F0F_0F0F,
        "corrupt": 0,
    })
    await agent._edge()
    await agent.pulse_request(req, PrefetchRequest(0, 0, 0, 0), model.CASE_CONFLICT)
    await agent._edge()
    await agent._edge()
    agent.miss_driver.set({
        "valid": 0, "blkPAddr": 0, "vSetIdx": 0, "waymask": 0,
        "maybeRvcMap": 0, "corrupt": 0,
    })
    observed = await agent.wait_result(
        model.predict(req, PrefetchRequest(0, 0, 0, 0),
                      itlb=itlb_hit(), meta=meta), check=False)
    for _ in range(6):
        await agent._edge()
    assert observed.writes[0].valid == 1
    assert observed.writes[0].waymask == (0, 0b0010)
    assert observed.writes[0].rvc == (0, 0x0F0F_0F0F)


@pytest.mark.feature("ICACHE-PREFETCHPIPE-012")
async def test_bpu_stage2_redirect_kills_the_prefetch(prefetchpipe_agent):
    """A redirect at or before the request stops it in stage 0."""
    agent = prefetchpipe_agent
    req = make_prefetch(0x2600, 15, ftq_idx=11)
    result = await agent.send(req, itlb=itlb_hit(), meta=miss_meta(),
                              bpu_s2=(0, 11))
    assert result is None, "the flushed prefetch must not write or request"


@pytest.mark.feature("ICACHE-PREFETCHPIPE-012")
async def test_bpu_stage3_redirect_kills_the_prefetch(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req = make_prefetch(0x2620, 15, ftq_idx=11)
    result = await agent.send(req, itlb=itlb_hit(), meta=miss_meta(),
                              bpu_s3=(0, 10))
    assert result is None


@pytest.mark.feature("ICACHE-PREFETCHPIPE-012")
async def test_soft_prefetch_is_exempt_from_the_bpu_redirect(prefetchpipe_agent):
    """A retired prefetch.i is not on the fetched path, so a BPU redirect at
    the same FTQ index must not drop it (RTL: ``!isSoftPrefetch`` gate)."""
    agent = prefetchpipe_agent
    req = make_prefetch(0x2640, 15, soft=1)
    observed = await agent.send(req, itlb=itlb_hit(), meta=miss_meta(),
                                bpu_s2=(0, req.ftq_idx))
    assert observed is not None
    assert observed.misses, "the soft prefetch must still request its line"


@pytest.mark.feature("ICACHE-PREFETCHPIPE-012")
async def test_bpu_stage3_redirect_kills_a_request_waiting_in_stage1(prefetchpipe_agent):
    """A stage-3 redirect flushes a request held in stage 1 by an ITLB miss."""
    agent = prefetchpipe_agent
    req = make_prefetch(0x2660, 15, ftq_idx=11)
    agent.drive_itlb(model.ItlbResponse(miss=1))
    agent.drive_meta(miss_meta())
    agent.pmp_driver.set({"instr": 0, "mmio": 0})
    await agent._edge()
    await agent.pulse_request(req, PrefetchRequest(0, 0, 0, 0),
                              model.CASE_CONFLICT)
    await agent._edge()
    agent.bpu_driver.set(agent._bpu_payload(None, (0, 11)))
    seen_flush = 0
    for _ in range(10):
        seen_flush |= agent.itlb_flush_pipe()
        assert agent.way_valid(0) == 0, "a flushed stage-1 request wrote the queue"
        await agent._edge()
    agent.bpu_driver.set(agent._bpu_idle())
    assert seen_flush == 1, "the ITLB pipeline must be flushed with stage 1"


@pytest.mark.feature("ICACHE-PREFETCHPIPE-013")
async def test_corrupt_refill_is_not_a_hit_and_does_not_update_metadata(prefetchpipe_agent):
    """A corrupt refill must leave the requested line missing.

    The miss unit returns the correct block/set with ``corrupt=1``; because the
    line was not installed, the prefetch must still request it and the queued
    way mask must stay empty (the RTL gates every merge with
    ``~io_missResp_bits_corrupt``).
    """
    agent = prefetchpipe_agent
    req = make_prefetch(0x2680, 15)
    agent.drive_itlb(itlb_hit())
    agent.drive_meta(miss_meta())
    agent.miss_driver.set({
        "valid": 1,
        "blkPAddr": model.get_blk_addr(PTAG, req.vaddr),
        "vSetIdx": model.get_idx(req.vaddr),
        "waymask": 0b0100,
        "maybeRvcMap": 0xDEAD_BEEF,
        "corrupt": 1,
    })
    await agent._edge()
    await agent.pulse_request(req, PrefetchRequest(0, 0, 0, 0),
                              model.CASE_CONFLICT)
    await agent._edge()
    await agent._edge()
    agent.miss_driver.set({
        "valid": 0, "blkPAddr": 0, "vSetIdx": 0, "waymask": 0,
        "maybeRvcMap": 0, "corrupt": 0,
    })
    expected = model.predict(req, PrefetchRequest(0, 0, 0, 0),
                             itlb=itlb_hit(), meta=miss_meta())
    observed = await agent.wait_result(expected, check=False)
    # Only line 0 is defined for a non-cross fetch; line 1 may hold stale
    # metadata that the main pipe never consumes.
    assert observed.writes[0].waymask[0] == 0
    assert observed.misses == expected.misses
    assert observed.misses, "a corrupt refill must not suppress the miss"


@pytest.mark.feature("ICACHE-PREFETCHPIPE-013")
async def test_refill_of_another_line_does_not_update_metadata(prefetchpipe_agent):
    """A refill is matched by set and tag, not just by arriving at stage 1."""
    agent = prefetchpipe_agent
    req = make_prefetch(0x26C0, 15)
    other = make_prefetch(0x2720, 15)
    agent.drive_itlb(itlb_hit())
    agent.drive_meta(miss_meta())
    agent.miss_driver.set({
        "valid": 1,
        # A different page: the page tag must not match, so this refill is
        # unrelated even though its set index could coincide with a line of
        # the requested page.
        "blkPAddr": model.get_blk_addr(PTAG + 1, other.vaddr),
        "vSetIdx": model.get_idx(other.vaddr),
        "waymask": 0b0100,
        "maybeRvcMap": 0x0BAD_F00D,
        "corrupt": 0,
    })
    await agent._edge()
    await agent.pulse_request(req, PrefetchRequest(0, 0, 0, 0),
                              model.CASE_CONFLICT)
    await agent._edge()
    await agent._edge()
    agent.miss_driver.set({
        "valid": 0, "blkPAddr": 0, "vSetIdx": 0, "waymask": 0,
        "maybeRvcMap": 0, "corrupt": 0,
    })
    expected = model.predict(req, PrefetchRequest(0, 0, 0, 0),
                             itlb=itlb_hit(), meta=miss_meta())
    observed = await agent.wait_result(expected, check=False)
    assert observed.writes[0].waymask[0] == 0
    assert observed.misses == expected.misses
    assert observed.misses


@pytest.mark.feature("ICACHE-PREFETCHPIPE-007")
async def test_backend_exception_codes_are_carried(prefetchpipe_agent):
    agent = prefetchpipe_agent
    for code in (1, 2, 3):
        req = make_prefetch(0x2700 + 0x40 * code, 15, backend=code)
        observed = await agent.send(req, itlb=itlb_hit(), meta=miss_meta())
        assert observed.writes[0].exception == code
        assert observed.misses == ()


@pytest.mark.feature("ICACHE-PREFETCHPIPE-012")
async def test_bpu_redirect_pointer_sweep(prefetchpipe_agent):
    """Sweep both pointers so every flag/value bit and both wrap directions run."""
    agent = prefetchpipe_agent
    ftq = 9
    for flag in (0, 1):
        for value in (0, 1, 2, 4, 8, 9, 10, 16, 31, 32, 63):
            req = make_prefetch(0x2800, 15, ftq_idx=ftq)
            # !isAfter((flag,value), (0,9)) decides suppression.
            is_after = (flag ^ 0) ^ int(value > ftq)
            killed = not is_after
            pointer = ({"bpu_s2": (flag, value)} if value % 2 == 0
                       else {"bpu_s3": (flag, value)})
            observed = await agent.send(
                req, itlb=itlb_hit(), meta=hit_meta(0), **pointer)
            if killed:
                assert observed is None, (
                    f"redirect({flag},{value}) must suppress FTQ {ftq}")
            else:
                assert observed is not None, (
                    f"redirect({flag},{value}) must leave FTQ {ftq} alone")


@pytest.mark.feature("ICACHE-PREFETCHPIPE-012")
async def test_bpu_stage3_wrapped_pointer_is_compared(prefetchpipe_agent):
    agent = prefetchpipe_agent
    req = make_prefetch(0x2A00, 15, ftq_idx=9)
    # flag=1 value=0 is after FTQ 9 under the circular compare, so it survives.
    observed = await agent.send(req, itlb=itlb_hit(), meta=hit_meta(0),
                                bpu_s3=(1, 0))
    assert observed is not None
    # flag=0 value=9 is at the target, so it is killed.
    req = make_prefetch(0x2A40, 15, ftq_idx=9)
    killed = await agent.send(req, itlb=itlb_hit(), meta=hit_meta(0),
                              bpu_s3=(0, 9))
    assert killed is None


@pytest.mark.feature("ICACHE-PREFETCHPIPE-011")
async def test_two_misses_from_one_prefetch_pair(prefetchpipe_agent):
    """Both prefetch requests miss: the second miss arbiter port is used."""
    agent = prefetchpipe_agent
    req0 = make_prefetch(0x2B00, 15, ftq_idx=1)
    req1 = make_prefetch(0x2B80, 15, ftq_idx=2)
    observed = await agent.send(req0, req1, case=model.CASE_INTERLEAVE,
                                itlb=itlb_hit(), meta=miss_meta(),
                                distinct_misses=True)
    assert observed.writes[0].valid and observed.writes[1].valid
    assert len(observed.misses) == 2
    assert len(set(observed.misses)) == 2, (
        f"the arbiter re-presented one request instead of issuing both: "
        f"{observed.misses}")
    # Let stage 2 retire and its per-port hasSend registers fall.
    for _ in range(6):
        await agent._edge()


@pytest.mark.feature("ICACHE-PREFETCHPIPE-014")
async def test_refill_in_stage2_satisfies_the_request_without_issuing(prefetchpipe_agent):
    """A miss response that arrives while the request is in stage 2 makes it
    finish without a new miss request (the MSHR hit is latched in s2)."""
    agent = prefetchpipe_agent
    req = make_prefetch(0x2C00, 15)
    agent.miss_ready_driver.set({"ready": 0})
    await agent._edge()
    agent.drive_itlb(itlb_hit())
    agent.drive_meta(miss_meta())
    agent.pmp_driver.set({"instr": 0, "mmio": 0})
    await agent._edge()
    await agent.pulse_request(req, PrefetchRequest(0, 0, 0, 0),
                              model.CASE_CONFLICT)
    for _ in range(12):
        if agent.miss_valid():
            break
        await agent._edge()
    assert agent.miss_valid() == 1, "the request must reach the miss request stage"

    agent.miss_driver.set({
        "valid": 1,
        "blkPAddr": model.get_blk_addr(PTAG, req.vaddr),
        "vSetIdx": model.get_idx(req.vaddr),
        "waymask": 0b0100,
        "maybeRvcMap": 0x1234_5678,
        "corrupt": 0,
    })
    for _ in range(10):
        await agent._edge()
        if not agent.miss_valid():
            break
    agent.miss_driver.set({
        "valid": 0, "blkPAddr": 0, "vSetIdx": 0, "waymask": 0,
        "maybeRvcMap": 0, "corrupt": 0,
    })
    agent.miss_ready_driver.set({"ready": 1})
    assert agent.miss_valid() == 0, (
        "a stage-2 refill must satisfy the request without a miss handshake")
    for _ in range(6):
        await agent._edge()
    assert agent.ftq_ready() == 1, "the pipe must accept the next request"


@pytest.mark.feature("ICACHE-PREFETCHPIPE-014")
async def test_second_line_refill_in_stage2_suppresses_only_that_miss(prefetchpipe_agent):
    """A cross-line request sees line 1's refill while waiting in stage 2.

    The refill satisfies the second line (`s2_mshrHits(1)`), so releasing the
    miss unit afterwards must issue only the first line's miss request.
    """
    agent = prefetchpipe_agent
    req = make_prefetch(0x3020, 31)
    assert req.is_cross_line == 1
    agent.miss_ready_driver.set({"ready": 0})
    await agent._edge()
    agent.drive_itlb(itlb_hit())
    agent.drive_meta(miss_meta())
    agent.pmp_driver.set({"instr": 0, "mmio": 0})
    await agent._edge()
    await agent.pulse_request(req, PrefetchRequest(0, 0, 0, 0),
                              model.CASE_CONFLICT)
    for _ in range(12):
        if agent.miss_valid():
            break
        await agent._edge()
    assert agent.miss_valid() == 1

    next_block = model.get_blk_addr(PTAG, req.next_vaddr)
    agent.miss_driver.set({
        "valid": 1,
        "blkPAddr": next_block,
        "vSetIdx": req.vset[1],
        "waymask": 0b0010,
        "maybeRvcMap": 0xCAFE_1234,
        "corrupt": 0,
    })
    for _ in range(8):
        await agent._edge()
    observed_misses = []
    agent.miss_ready_driver.set({"ready": 1})
    for _ in range(16):
        if agent.miss_valid():
            observed_misses.append(
                (agent._value(agent.ports.miss_req, "blkPAddr"),
                 agent._value(agent.ports.miss_req, "vSetIdx")))
        await agent._edge()
    agent.miss_driver.set({
        "valid": 0, "blkPAddr": 0, "vSetIdx": 0, "waymask": 0,
        "maybeRvcMap": 0, "corrupt": 0,
    })
    # Only line 0 may be requested; line 1 was already refilled.
    assert observed_misses, "line 0 must still request its miss"
    assert all(vset == req.vset[0] for _, vset in observed_misses), (
        f"line 1 was re-requested although it was refilled: {observed_misses}")


@pytest.mark.feature("ICACHE-PREFETCHPIPE-009")
async def test_second_request_can_cross_the_line(prefetchpipe_agent):
    """req1 may be the cross-line block of a same-line pair."""
    agent = prefetchpipe_agent
    req0 = make_prefetch(0x3100, 7, ftq_idx=1)
    req1 = make_prefetch(0x3130, 31, ftq_idx=2)
    assert req0.is_cross_line == 0 and req1.is_cross_line == 1
    meta = hit_meta(0)
    observed = await agent.send(req0, req1, case=model.CASE_SAME_LINE,
                                itlb=itlb_hit(), meta=meta)
    assert observed.meta_double == 1
    assert observed.writes[0].valid == 1 and observed.writes[1].valid == 1


@pytest.mark.feature("ICACHE-PREFETCHPIPE-002")
async def test_cross_line_request_issues_both_line_misses(prefetchpipe_agent):
    """A cross-line prefetch requests both lines, one after the other.

    The second line's miss request is the second arbiter input and the second
    ``s2_hasSend`` slot; the two requests are issued from the same fetch.
    """
    agent = prefetchpipe_agent
    req = make_prefetch(0x3200 + 0x20, 31)
    assert req.is_cross_line == 1
    agent.drive_itlb(itlb_hit())
    agent.drive_meta(miss_meta())
    observed = await agent.send(req, itlb=itlb_hit(), meta=miss_meta(),
                                distinct_misses=True)
    assert observed.writes[0].valid == 1
    assert len(observed.misses) == 2, (
        f"both lines must be requested, got {observed.misses}")
    assert {vset for _, vset in observed.misses} == set(req.vset)
    for _ in range(6):
        await agent._edge()


@pytest.mark.feature("ICACHE-PREFETCHPIPE-010")
async def test_port1_hit_then_miss_clears_the_stage2_hit_flags(prefetchpipe_agent):
    """Both request slots' stage-2 hit registers fall after a miss."""
    agent = prefetchpipe_agent
    hit0 = make_prefetch(0x3500, 15, ftq_idx=1)
    hit1 = make_prefetch(0x3580, 15, ftq_idx=2)
    await agent.send(hit0, hit1, case=model.CASE_INTERLEAVE,
                     itlb=itlb_hit(), meta=hit_meta(0))
    miss0 = make_prefetch(0x3600, 15, ftq_idx=3)
    miss1 = make_prefetch(0x3680, 15, ftq_idx=4)
    observed = await agent.send(miss0, miss1, case=model.CASE_INTERLEAVE,
                                itlb=itlb_hit(), meta=miss_meta(),
                                distinct_misses=True)
    assert len(set(observed.misses)) == 2


@pytest.mark.feature("ICACHE-PREFETCHPIPE-010")
async def test_hit_then_miss_clears_the_stage1_hit_registers(prefetchpipe_agent):
    """The registered stage-1 hit flags fall after a miss follows a hit."""
    agent = prefetchpipe_agent
    hit_req = make_prefetch(0x3400, 15)
    await agent.send(hit_req, itlb=itlb_hit(), meta=hit_meta(0))
    miss_req = make_prefetch(0x3440, 15)
    observed = await agent.send(miss_req, itlb=itlb_hit(), meta=miss_meta())
    assert observed.writes[0].waymask == (0, 0)
    assert len(observed.misses) == 1
