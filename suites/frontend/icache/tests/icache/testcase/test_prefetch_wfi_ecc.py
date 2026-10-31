"""Prefetch, WFI and ECC-control behaviour of the whole ICache."""

from __future__ import annotations

import pytest

from suites.frontend.icache.icache.agent.main import ECC_CTRL
from suites.frontend.icache.icache.agent.main import ECC_ENABLE
from suites.frontend.icache.icache.agent.main import ECC_IADDR
from suites.frontend.icache.icache.agent.main import ECC_INJECT
from suites.frontend.icache.icache.agent.main import ECC_TARGET_DATA
from suites.frontend.icache.icache.case.definitions import CASE_INTERLEAVE
from suites.frontend.icache.icache.case.definitions import make_fetch
from suites.frontend.icache.icache.model import icache as model


async def _wait_memory_idle(agent, extra: int = 10) -> None:
    for _ in range(64):
        if (not agent._pending and agent._current is None
                and not agent.mem_a_valid()):
            break
        await agent._edge()
    for _ in range(extra):
        await agent._edge()


@pytest.mark.xfail(strict=True, reason=(
    "RTL defect in ICacheImp: softPrefetch_vSetIdx_0 is latched from the "
    "previous startVAddr register, so prefetch.i installs the line in the "
    "wrong set and the following demand fetch misses"))
@pytest.mark.feature("ICACHE-ICACHE-012")
async def test_software_prefetch_warms_the_requested_line(icache_agent):
    """prefetch.i must make the following demand fetch of that line a hit.

    Defect evidence (generated ``ICacheDut.v``)::

        if (_GEN) begin
          softPrefetch_startVAddr_addr <= {pc_addr[48], pc_addr};
          softPrefetch_vSetIdx_0 <= softPrefetch_startVAddr_addr[12:5];
        end

    The set index is taken from the *pre-update* start-address register, so the
    first soft prefetch after reset uses set 0 and every later one reuses the
    previous request's set.  The block/tag and the miss request are correct, so
    the line is installed in an unreachable set: the demand fetch still misses.
    """
    # Control: a line whose own set index is 0 coincides with the stale value.
    control = 0x8000
    assert model.get_idx(control) == 0
    acquires = await icache_agent.soft_prefetch(control)
    assert [acq[0] for acq in acquires] == [control >> 6]
    icache_agent.model.install(control >> 6, model.get_idx(control))
    before = len(icache_agent.acquires)
    await icache_agent.send(make_fetch(control, 15))
    assert len(icache_agent.acquires) == before, (
        "control: a set-0 line is warmed by prefetch.i")

    # The requirement: a line in any other set must be warmed as well.
    vaddr = 0xB000                      # set 0xC0
    block = vaddr >> 6
    acquires = await icache_agent.soft_prefetch(vaddr)
    assert [acq[0] for acq in acquires] == [block]
    before = len(icache_agent.acquires)
    await icache_agent.send(make_fetch(vaddr, 15))
    assert len(icache_agent.acquires) == before, (
        "prefetch.i must warm the line in the set named by its own address")


@pytest.mark.feature("ICACHE-ICACHE-013")
async def test_wfi_safe_tracks_outstanding_misses(icache_agent):
    agent = icache_agent
    assert agent.wfi_safe() == 1, "an idle cache is WFI safe"

    req = make_fetch(0xC000, 15)
    absent = model.mp.FetchRequest(0, 0, 0, 0, valid=0)
    itlb = agent.itlb_translate(req.vaddr)
    expected = agent.model.expect(req, absent, itlb=itlb)
    agent.expected_fills = dict(expected.fill_by_block)
    agent.itlb_answer = itlb
    agent.auto_memory = False
    await agent._accept_fetch(req, absent, 0)
    await agent.wait_for(lambda: agent.mem_a_valid() == 1, what="the miss acquire")
    await agent.wait_for(lambda: agent.wfi_safe() == 0,
                         what="an issued miss to block WFI")

    agent.auto_memory = True
    for _ in range(40):
        if agent.ifu_valid():
            break
        await agent._edge()
    observed = agent.sample_ifu()
    agent.last_observed = observed
    await agent._edge()
    agent.model.commit_fill(expected.fills[0])
    assert agent.wfi_safe() == 1, "WFI is safe again once the refill completes"


@pytest.mark.feature("ICACHE-ICACHE-013")
async def test_wfi_request_holds_the_memory_acquire(icache_agent):
    agent = icache_agent
    req = make_fetch(0xC400, 15)
    absent = model.mp.FetchRequest(0, 0, 0, 0, valid=0)
    itlb = agent.itlb_translate(req.vaddr)
    expected = agent.model.expect(req, absent, itlb=itlb)
    agent.expected_fills = dict(expected.fill_by_block)
    agent.itlb_answer = itlb
    agent.auto_memory = False
    await agent.set_wfi(1)
    await agent._accept_fetch(req, absent, 0)
    before = len(agent.acquires)
    for _ in range(10):
        assert agent.mem_a_valid() == 0, "wfiReq must hold back a new acquire"
        assert len(agent.acquires) == before, "no acquire may be accepted"
        await agent._edge()
    await agent.set_wfi(0)
    await agent.wait_for(lambda: len(agent.acquires) > before,
                         what="the acquire after WFI release")
    assert agent.acquires[before][0] == req.vaddr >> 6


@pytest.mark.feature("ICACHE-ICACHE-014")
async def test_ecc_control_register_reads_and_writes(icache_agent):
    agent = icache_agent
    value = await agent.ctrl_read(ECC_CTRL)
    assert value & ECC_ENABLE == 1, "ECC checking is enabled after reset"

    await agent.ctrl_write(ECC_CTRL, 0)
    assert await agent.ctrl_read(ECC_CTRL) & ECC_ENABLE == 0
    await agent.ctrl_write(ECC_CTRL, ECC_ENABLE)
    assert await agent.ctrl_read(ECC_CTRL) & ECC_ENABLE == 1

    # Injecting with ECC disabled must be refused with the NotEnabled error.
    await agent.ctrl_write(ECC_CTRL, ECC_INJECT | ECC_TARGET_DATA)
    status = await agent.ctrl_read(ECC_CTRL)
    assert (status >> 4) & 0b111 == 7, "injection without ECC must report an error"
    assert (status >> 7) & 0b111 == 0, "the error code must be NotEnabled"
    # An invalid injection target must be refused with TargetInvalid (1).
    await agent.ctrl_write(ECC_CTRL, ECC_ENABLE | ECC_INJECT | (1 << 2))
    status = await agent.ctrl_read(ECC_CTRL)
    assert (status >> 4) & 0b111 == 7
    assert (status >> 7) & 0b111 == 1, "the error code must be TargetInvalid"

    # Injecting an address that is not cached must fail with NotFound (2).
    await agent.ctrl_write(ECC_IADDR, 0x3_0000)
    await agent.ctrl_write(ECC_CTRL, ECC_ENABLE | ECC_INJECT | ECC_TARGET_DATA)
    for _ in range(12):
        status = await agent.ctrl_read(ECC_CTRL)
        state = (status >> 4) & 0b111
        if state == 7:
            break
    assert state == 7 and ((status >> 7) & 0b111) == 2, (
        f"injecting an absent line must report NotFound, got {status:#x}")
    await agent.ctrl_write(ECC_CTRL, ECC_ENABLE)


@pytest.mark.feature("ICACHE-ICACHE-014")
async def test_ecc_meta_injection_completes(icache_agent):
    """The control unit can also poison a metadata entry."""
    agent = icache_agent
    vaddr = 0xE000
    await agent.send(make_fetch(vaddr, 15))
    await agent.ctrl_write(ECC_IADDR, vaddr)
    await agent.ctrl_write(ECC_CTRL, ECC_ENABLE | ECC_INJECT)  # target MetaArray
    state = 0
    for _ in range(12):
        status = await agent.ctrl_read(ECC_CTRL)
        state = (status >> 4) & 0b111
        if state in (2, 7):
            break
    assert state == 2, f"metadata injection did not complete: {status:#x}"
    await agent.ctrl_write(ECC_CTRL, ECC_ENABLE)


@pytest.mark.feature("ICACHE-ICACHE-014")
async def test_ecc_injection_reports_a_cache_error(icache_agent):
    agent = icache_agent
    vaddr = 0xD000
    second = 0xD040               # the second line of a fetch at 0xD020
    await agent.send(make_fetch(vaddr, 15))
    await agent.send(make_fetch(second, 15))
    await agent.inject_ecc_error(vaddr)
    await agent.inject_ecc_error(second)

    # Banks 0..3 of the poisoned line.  The instruction bytes of a line whose
    # ECC is corrupt are not architectural; the corrupt flag and the BEU report
    # are the result, and every other response field is still compared.
    observed = await agent.send(make_fetch(vaddr, 15), undefined=("data",))
    assert observed.blocks[0].data == 0
    assert agent.last_corrupt[0] == 1, "toIfu.corrupt must flag the fetched port"
    assert agent.last_error_valid == 1, "the error must be reported to the BEU"
    assert agent.last_error_paddr == vaddr

    # Banks 4..7 of the same line.
    observed = await agent.send(make_fetch(vaddr + 0x20, 15),
                                undefined=("data",))
    assert agent.last_corrupt[0] == 1

    # A cross-line fetch whose *second* line is the other poisoned block.
    observed = await agent.send(make_fetch(vaddr + 0x20, 31),
                                undefined=("data",))
    assert agent.last_corrupt[0] == 1
    assert agent.last_corrupt[1] == 1, (
        "the second line's corrupt flag must be raised as well")
    assert agent.last_error_valid == 1

    # A dual fetch: request 0 hits the second poisoned line, request 1 crosses
    # from the first poisoned line into it.  This raises the corrupt flags of
    # the second request as well.
    await agent.send(make_fetch(vaddr, 15), undefined=("data",))  # warm line 0
    observed = await agent.send(
        make_fetch(second, 15), make_fetch(vaddr + 0x20, 31),
        undefined=("data",))
    assert observed.two_fetch_valid == 1
    assert agent.last_corrupt[0] == 1   # request 0, its line 0
    assert agent.last_corrupt[2] == 1   # request 1, its line 0
    assert agent.last_corrupt[3] == 1   # request 1, its line 1
    assert agent.last_error_valid == 1


@pytest.mark.feature("ICACHE-ICACHE-026")
async def test_all_prefetch_mshrs_hold_outstanding_misses(icache_agent):
    """Saturate the ten prefetch MSHRs, then release all refills.

    The miss unit must allocate a distinct prefetch MSHR for each outstanding
    line, hold them until the memory channel drains, and install every line.
    """
    agent = icache_agent
    agent.auto_memory = False
    agent.allow_unexpected = True
    addresses = [0x70000 + index * 0x40 for index in range(10)]
    try:
        for address in addresses:
            await agent.prefetch_only(make_fetch(address, 15), settle=10)
        assert len(agent.acquires) == 10, (
            f"expected 10 outstanding acquires, got {agent.acquires}")
        sources = {source for _, source in agent.acquires}
        assert sources == set(range(4, 14)), (
            f"prefetch MSHRs 4..13 must all be used, got {sorted(sources)}")
        agent.auto_memory = True
        for _ in range(200):
            await agent._edge()
            if not agent._pending and agent._current is None:
                break
        for _ in range(20):
            await agent._edge()
        await agent.redirect_flush()
        for address in addresses:
            block = address >> 6
            agent.model.install(block, model.get_idx(address))
            before = len(agent.acquires)
            observed = await agent.send(make_fetch(address, 15))
            assert len(agent.acquires) == before, f"{address:#x} was not installed"
            assert (observed.blocks[0].data & ((1 << 256) - 1)
                    == model.memory_data(block) & ((1 << 256) - 1))
    finally:
        agent.auto_memory = True
        agent.allow_unexpected = False


@pytest.mark.feature("ICACHE-ICACHE-015")
async def test_hardware_prefetch_fills_the_demand_path(icache_agent):
    """The FTQ prefetch of a fetch issue owns the fill for the demand fetch."""
    agent = icache_agent
    req = make_fetch(0xF000, 15)
    first = await agent.send(req)
    assert len(agent.acquires) == 1
    block, source = agent.acquires[0]
    assert source >= 4, (
        "the line must be fetched by the prefetch pipe's MSHR (4..13), "
        f"got source {source}")
    before = len(agent.acquires)
    second = await agent.send(req)
    assert len(agent.acquires) == before, "the demand fetch must hit"
    assert (second.blocks[0].data & ((1 << 256) - 1)
            == (first.blocks[0].data & ((1 << 256) - 1)))


@pytest.mark.feature("ICACHE-ICACHE-029")
async def test_soft_prefetch_is_accepted_from_each_ldu_port(icache_agent):
    """Any of the three load-unit ports can retire prefetch.i.

    The hint priority mux (port 0 > 1 > 2) has a separate arm for each lower
    port.  The block address of the resulting acquire is independent of the
    known vSetIdx defect, so each port must request the hinted line.
    """
    agent = icache_agent
    for port, vaddr in ((1, 0xC000), (2, 0xD000)):
        acquires = await agent.soft_prefetch(vaddr, port=port)
        assert [acq[0] for acq in acquires] == [vaddr >> 6], (
            f"port {port} prefetched the wrong block")


@pytest.mark.xfail(strict=True, reason=(
    "RTL defect in ICacheImp: while a soft prefetch is pending, the FTQ "
    "prefetch issue's req(1) is processed although fromFtq.toPrefetch.ready "
    "is low; upstream issue #6674, removed by PR #6691"))
@pytest.mark.feature("ICACHE-ICACHE-030")
async def test_pending_soft_prefetch_does_not_process_an_unaccepted_ftq_issue(
        icache_agent):
    """An unaccepted FTQ prefetch issue must not touch the memory system.

    ``ICacheImp`` merges a pending software prefetch into the *prefetch* pipe's
    request by replacing ``req(0)``, but it leaves ``req(1)`` and
    ``twoPrefetchCase`` from the FTQ issue and only gates ``toPrefetch.ready``
    with ``!softPrefetchValid``.  A decoupled producer may therefore observe
    ``ready = 0`` forever while its second block is still prefetched (and, when
    the two blocks are in different pages, translated with the soft prefetch's
    page tag).  Upstream reports the same root cause as issue #6674 (a
    ``prefetch.i`` program aborting on the meta-array bank assertion) and
    removes the ICache-top selection in PR #6691.
    """
    agent = icache_agent
    previous = agent.allow_unexpected
    agent.allow_unexpected = True
    try:
        # Keep the soft prefetch asserted so softPrefetchValid stays high.
        agent.soft_driver.set({"valid0": 1, "vaddr0": 0x4080,
                               "valid1": 0, "vaddr1": 0,
                               "valid2": 0, "vaddr2": 0})
        await agent._edge()
        await agent._edge()
        # Interleave is legal for req0 odd (0x4040 -> set 0x01) and req1 even
        # (0x4000 -> set 0x00); the soft prefetch's stale set is 0 (even), so
        # the merged meta read even violates the interleaved-bank rule.
        req0 = make_fetch(0x4040, 15)
        req1 = make_fetch(0x4000, 15)
        agent.ftq_pref_driver.set(agent._pref_payload(req0, req1,
                                                      CASE_INTERLEAVE))
        start = len(agent.acquires)
        for _ in range(24):
            assert agent._bit(agent.ports.ftq_pref_ready) == 0, (
                "the FTQ issue became accepted; the test premise no longer holds")
            await agent._edge()
        blocks = [block for block, _ in agent.acquires[start:]]
        # req0 = 0x4040 -> block 0x101, req1 = 0x4000 -> block 0x100,
        # soft  = 0x4080 -> block 0x102.
        assert 0x101 not in blocks, (
            f"an unaccepted FTQ req0 was prefetched (acquires={blocks})")
        assert 0x100 not in blocks, (
            "the FTQ issue's second block was prefetched although the issue "
            f"never completed its handshake (acquires={blocks})")
    finally:
        agent.soft_driver.set({"valid0": 0, "vaddr0": 0,
                               "valid1": 0, "vaddr1": 0,
                               "valid2": 0, "vaddr2": 0})
        agent.ftq_pref_driver.set(
            {key: 0 for key in agent.ports.ftq_pref.bits.fields})
        agent.allow_unexpected = previous


@pytest.mark.feature("ICACHE-ICACHE-029")
async def test_soft_prefetch_fetches_only_the_hinted_block(icache_agent):
    """A software prefetch must not touch any other block.

    The agent tolerates the hinted line's acquire during the hint window but
    records every unpredicted acquire; this test pins the contract that the
    window contains exactly the hinted block.
    """
    agent = icache_agent
    acquires = await agent.soft_prefetch(0xE000)
    hinted = 0xE000 >> 6
    assert [block for block, _ in acquires] == [hinted]
    # The demand model predicts no fill here, so the hint's own line is the one
    # "unexpected" acquire; nothing else may appear.
    assert all(block == hinted for block, _ in agent.unexpected), (
        f"a software prefetch fetched unrelated blocks: "
        f"{[hex(b) for b, _ in agent.unexpected if b != hinted]}")
