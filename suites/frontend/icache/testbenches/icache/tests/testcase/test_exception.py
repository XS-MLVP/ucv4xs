"""Exception and error paths through the whole ICache."""

from __future__ import annotations

import pytest

from suites.frontend.icache.testbenches.icache.tests.scenarios.definitions import make_fetch
from suites.frontend.icache.testbenches.icache.model import icache as model
from suites.frontend.icache.testbenches.icache.model.icache import ItlbAnswer


@pytest.mark.feature("ICACHE-ICACHE-009")
async def test_itlb_page_fault_is_reported_without_a_fetch(icache_agent):
    agent = icache_agent
    req = make_fetch(0x8000, 15)
    itlb = ItlbAnswer(paddr=0x8000, pf=1, gpaddr=0x1234_5000)
    observed = await agent.send(req, itlb=itlb)
    assert observed.ifu_valid == 1
    assert observed.blocks[0].exception == model.EXC_PF
    assert observed.blocks[0].gpaddr == 0x1234_5000
    assert agent.acquires == [], "an ITLB fault must not fetch from memory"


@pytest.mark.feature("ICACHE-ICACHE-009")
async def test_itlb_guest_page_fault_and_access_fault_map_to_their_exceptions(icache_agent):
    agent = icache_agent
    observed = await agent.send(
        make_fetch(0x8400, 15),
        itlb=ItlbAnswer(paddr=0x8400, gpf=1, gpaddr=0x4000_0000))
    assert observed.blocks[0].exception == model.EXC_GPF

    observed = await agent.send(
        make_fetch(0x8800, 15), itlb=ItlbAnswer(paddr=0x8800, af=1))
    assert observed.blocks[0].exception == model.EXC_AF
    assert agent.acquires == []


@pytest.mark.feature("ICACHE-ICACHE-009")
async def test_backend_exception_is_forwarded(icache_agent):
    agent = icache_agent
    # The FTQ carries the back-end exception as an ExceptionType plus a flag.
    req = make_fetch(0x8C00, 15, has_backend_exception=1)
    req = model.mp.FetchRequest(
        vaddr=req.vaddr, next_vaddr=req.next_vaddr,
        end_position=req.end_position, ftq_idx=req.ftq_idx,
        bank_sel=req.bank_sel, vset=req.vset,
        has_backend_exception=1, backend_exception=model.EXC_PF, valid=1)
    observed = await agent.send(req)
    assert observed.blocks[0].backend_exception == 1
    assert observed.blocks[0].exception == model.EXC_PF, (
        "the back-end exception is forwarded as the fetch exception")


@pytest.mark.feature("ICACHE-ICACHE-010")
async def test_pmp_access_fault_is_reported(icache_agent):
    agent = icache_agent
    observed = await agent.send(make_fetch(0x9000, 15), pmp_instr=1)
    assert observed.blocks[0].exception == model.EXC_AF
    assert agent.acquires == []


@pytest.mark.feature("ICACHE-ICACHE-010")
async def test_mmio_fetch_is_not_cached(icache_agent):
    agent = icache_agent
    observed = await agent.send(make_fetch(0x9400, 15), pmp_mmio=1)
    assert observed.blocks[0].pmp_mmio == 1
    assert observed.blocks[0].exception == model.EXC_NONE
    assert agent.acquires == [], "MMIO must bypass the cache"


@pytest.mark.feature("ICACHE-ICACHE-010")
async def test_uncacheable_pbmt_is_not_cached(icache_agent):
    agent = icache_agent
    observed = await agent.send(
        make_fetch(0x9800, 15),
        itlb=ItlbAnswer(paddr=0x9800, pbmt=2))
    assert observed.blocks[0].itlb_pbmt == 2
    assert observed.blocks[0].pmp_mmio == 0, "only a PMP answer sets pmpMmio"
    assert agent.acquires == []


@pytest.mark.feature("ICACHE-ICACHE-011")
async def test_corrupt_refill_raises_a_hardware_error(icache_agent):
    agent = icache_agent
    req = make_fetch(0xA000, 15)
    observed = await agent.send(req, corrupt_refill=1)
    assert observed.blocks[0].exception == model.EXC_HWE
    assert len(agent.acquires) == 1


@pytest.mark.feature("ICACHE-ICACHE-011")
async def test_denied_refill_raises_an_access_fault(icache_agent):
    agent = icache_agent
    req = make_fetch(0xA400, 15)
    observed = await agent.send(req, denied_refill=1)
    assert observed.blocks[0].exception == model.EXC_AF
    assert len(agent.acquires) == 1


@pytest.mark.feature("ICACHE-ICACHE-027")
async def test_itlb_miss_holds_and_resends_the_prefetch(icache_agent):
    """An ITLB miss must stall the prefetch pipe and re-issue the request.

    While the translation is missing, the prefetch pipe keeps offering the
    address; once it is released the fetch proceeds normally.
    """
    agent = icache_agent
    req = make_fetch(0x62000, 15)
    absent = model.mp.FetchRequest(0, 0, 0, 0, valid=0)
    expected = agent.expect(req, absent,
                            itlb=agent.itlb_translate(req.vaddr))
    agent.expected_fills = dict(expected.fill_by_block)
    agent.itlb_answer = agent.itlb_translate(req.vaddr)
    agent.itlb_hold_miss = 1
    agent.set_csr_pf(1)
    agent.present_fetch(req, absent)
    await agent.tick()
    resends = 0
    for _ in range(6):
        if agent.itlb_request_valid():
            resends += 1
        await agent.tick()
    assert resends >= 2, "the prefetch pipe must keep asking while the ITLB misses"
    agent.itlb_hold_miss = 0
    # Let the decoupled handshake finish: each channel is held until its own
    # fire and dropped immediately (the next edge is the accept).
    await agent.accept_presented_fetch()
    observed = await agent.wait_response(expected)
    agent.commit_expectation(expected)
    agent.expected_fills = {}
    agent.itlb_answer = None
    assert observed.ifu_valid == 1
    assert (observed.blocks[0].data & ((1 << 256) - 1)
            == model.memory_data(req.vaddr >> 6) & ((1 << 256) - 1))
