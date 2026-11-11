"""Prefetch, WFI and ECC-control behaviour of the whole ICache."""

from __future__ import annotations

import pytest

from suites.frontend.icache.testbenches.icache.env.agent.main import ECC_CTRL
from suites.frontend.icache.testbenches.icache.env.agent.main import ECC_ENABLE
from suites.frontend.icache.testbenches.icache.env.agent.main import ECC_IADDR
from suites.frontend.icache.testbenches.icache.env.agent.main import ECC_INJECT
from suites.frontend.icache.testbenches.icache.env.agent.main import ECC_TARGET_DATA
from suites.frontend.icache.testbenches.icache.tests.scenarios.definitions import CASE_INTERLEAVE
from suites.frontend.icache.testbenches.icache.tests.scenarios.definitions import make_fetch
from suites.frontend.icache.testbenches.icache.model import icache as model


async def _wait_memory_idle(agent, extra: int = 10) -> None:
    for _ in range(64):
        if agent.memory_idle():
            break
        await agent.tick()
    for _ in range(extra):
        await agent.tick()


@pytest.mark.feature("ICACHE-ICACHE-012")
async def test_software_prefetch_warms_the_requested_line(icache_agent):
    """prefetch.i must make the following demand fetch of that line a hit.

    Historical defect (old baseline ``893e1580b``, generated ``ICacheDut.v``)::

        if (_GEN) begin
          softPrefetch_startVAddr_addr <= {pc_addr[48], pc_addr};
          softPrefetch_vSetIdx_0 <= softPrefetch_startVAddr_addr[12:5];
        end

    The set index came from the *pre-update* start-address register, so the line
    was installed in an unreachable set and the demand fetch missed.  Upstream
    ``4b9f938b7`` (#6691) deleted that register and the ICache-top selection;
    the FTQ's ``PrefetchQueue`` now derives ``vSetIdx`` from the queue entry's
    own address.  The requirement itself is unchanged and is what this test
    checks.

    Disposition (2026-11-08): the defect was fixed upstream by #6691 and this
    case is now a normal positive requirement (no strict XFAIL marker).  The
    old failure record stays in ``docs/spec/verification/error-review.md`` §1.1
    and the red/green control is recorded in
    ``docs/spec/verification/reports/baseline-update-a0c2a26cb.md`` §8:
    installing the hinted line in the
    stale set 0 makes this test fail, installing it in the request's own set
    makes it pass, so the assertion is discriminating rather than vacuous.
    """
    # Control: a line whose own set index is 0 coincides with the stale value.
    control = 0x8000
    assert model.get_idx(control) == 0
    acquires = await icache_agent.soft_prefetch(control)
    assert [acq[0] for acq in acquires] == [control >> 6]
    icache_agent.record_hint_fill(control >> 6, model.get_idx(control))
    before = len(icache_agent.acquires)
    await icache_agent.send(make_fetch(control, 15))
    assert len(icache_agent.acquires) == before, (
        "control: a set-0 line is warmed by prefetch.i")

    # The requirement: a line in any other set must be warmed as well.
    vaddr = 0xB000                      # set 0xC0
    block = vaddr >> 6
    acquires = await icache_agent.soft_prefetch(vaddr)
    assert [acq[0] for acq in acquires] == [block]
    # Record the effect the hint is required to have (installed in the set
    # named by its own address) before the demand fetch.  Without this the
    # demand model would predict a refill and the harness, not the RTL, would
    # decide the outcome.
    icache_agent.record_hint_fill(block, model.get_idx(vaddr))
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
    expected = agent.expect(req, absent, itlb=itlb)
    agent.expected_fills = dict(expected.fill_by_block)
    agent.itlb_answer = itlb
    agent.auto_memory = False
    await agent.accept_fetch(req, absent, 0)
    await agent.wait_for(lambda: agent.mem_a_valid() == 1, what="the miss acquire")
    await agent.wait_for(lambda: agent.wfi_safe() == 0,
                         what="an issued miss to block WFI")

    agent.auto_memory = True
    for _ in range(40):
        if agent.ifu_valid():
            break
        await agent.tick()
    observed = agent.sample_ifu()
    agent.last_observed = observed
    await agent.tick()
    agent.commit_fill(expected.fills[0])
    assert agent.wfi_safe() == 1, "WFI is safe again once the refill completes"


@pytest.mark.feature("ICACHE-ICACHE-013")
async def test_wfi_request_holds_the_memory_acquire(icache_agent):
    agent = icache_agent
    req = make_fetch(0xC400, 15)
    absent = model.mp.FetchRequest(0, 0, 0, 0, valid=0)
    itlb = agent.itlb_translate(req.vaddr)
    expected = agent.expect(req, absent, itlb=itlb)
    agent.expected_fills = dict(expected.fill_by_block)
    agent.itlb_answer = itlb
    agent.auto_memory = False
    await agent.set_wfi(1)
    await agent.accept_fetch(req, absent, 0)
    before = len(agent.acquires)
    for _ in range(10):
        assert agent.mem_a_valid() == 0, "wfiReq must hold back a new acquire"
        assert len(agent.acquires) == before, "no acquire may be accepted"
        await agent.tick()
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
            await agent.tick()
            if agent.memory_idle():
                break
        for _ in range(20):
            await agent.tick()
        await agent.redirect_flush()
        for address in addresses:
            block = address >> 6
            agent.record_hint_fill(block, model.get_idx(address))
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
    """A retired prefetch.i hint reaches the ICache through the FTQ queue.

    Upstream ``4b9f938b7`` (#6691) deleted the three load-unit hint ports and
    the port-priority mux from ``ICacheImp``.  The queue and its enqueue
    arbitration now live in the FTQ (``Ftq.scala:258`` enqueues from
    ``io.softPrefetch``; ``PrefetchQueue.scala`` is a multi-in/single-out
    queue), so the ICache owns one ``fromFtq.toPrefetch`` channel whose entries
    are tagged ``source = Sw`` for a hint.  This test pins that boundary: the
    DUT must not re-introduce per-LDU hint pins, and every queued hint must be
    accepted and fetch exactly the line it names.

    The nodeid is kept from the old baseline so the per-node comparison stays
    one-to-one; the "each LDU port" loop is now an FTQ-side obligation, and
    this case verifies the surviving ICache side of the same function point.
    """
    agent = icache_agent
    assert not agent.has_published_port("softPrefetchReq"), (
        "per-LDU soft-prefetch pins belong to the FTQ queue, not the ICache")
    for vaddr in (0xC000, 0xD000):
        acquires = await agent.soft_prefetch(vaddr)
        assert [acq[0] for acq in acquires] == [vaddr >> 6], (
            f"the queued hint for {vaddr:#x} prefetched the wrong block")


@pytest.mark.feature("ICACHE-ICACHE-030")
async def test_pending_soft_prefetch_does_not_process_an_unaccepted_ftq_issue(
        icache_agent):
    """An unaccepted FTQ prefetch issue must not touch the memory system.

    Interface-migration contract; the successor of the retired ICache-top merge
    is the FTQ ``PrefetchQueue`` (``Ftq.scala`` enqueues ``io.softPrefetch``,
    ``PrefetchQueue.scala`` is its multi-in/single-out queue).  Upstream
    ``4b9f938b7`` (#6691) deleted ``ICacheImp``'s ``softPrefetchValid`` mux and
    connects ``prefetcher.io.fromFtq <> io.fromFtq.toPrefetch`` directly, so the
    old "merge a hint into an unaccepted issue" stimulus no longer exists.

    What remains at this boundary is the decoupled-channel obligation: the FTQ
    may hold ``toPrefetch.valid`` while ``ready`` is low, and no block of that
    issue may be fetched until the handshake completes.  The case keeps its
    original nodeid and feature point; the retired defect and its upstream
    issue/PR are recorded in ``docs/spec/verification/error-review.md`` §1.2.
    """
    agent = icache_agent
    # Occupy the prefetch pipe with a queued Sw hint held by a missing ITLB
    # translation: the hint is accepted, then stalls, so the Fdip issue that
    # follows cannot complete its handshake.
    agent.itlb_hold_miss = 1
    try:
        await agent.soft_prefetch(0x4080)
        req0 = make_fetch(0x4040, 15)
        req1 = make_fetch(0x4000, 15)
        agent.present_prefetch_issue(req0, req1, case=CASE_INTERLEAVE)
        start = len(agent.acquires)
        for _ in range(24):
            assert agent.ftq_pref_ready() == 0, (
                "the FTQ issue became accepted; the test premise no longer holds")
            await agent.tick()
        blocks = [block for block, _ in agent.acquires[start:]]
        # req0 = 0x4040 -> block 0x101, req1 = 0x4000 -> block 0x100.
        assert blocks == [], (
            "an unaccepted FTQ prefetch issue reached the memory system: "
            f"{[(hex(block), source) for block, source in blocks]}")
    finally:
        # Let the held hint complete after the issue is withdrawn (its own
        # block is the only one it may fetch; the window tolerance is scoped
        # to this cleanup, not to the assertions above).
        agent.allow_unexpected = True
        agent.drop_fetch()
        agent.itlb_hold_miss = 0
        for _ in range(64):
            await agent.tick()
        agent.allow_unexpected = False


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


@pytest.mark.feature("ICACHE-ICACHE-014")
async def test_ecc_injection_waits_for_the_arrays_across_a_flush(icache_agent):
    """An injection must wait for the arrays instead of dropping its write.

    ``ICacheCtrlUnit`` issues a metadata read, then a metadata or data write.
    Both are accepted by the array's own ready, so during the per-row sweep of
    a ``fence.i`` the control unit must hold its state (the FSM's wait arms)
    and finish once the arrays are free.  Injection racing a flush is reachable
    from software through the ECC control register and ``fence.i``; the
    observable outcome is a terminal status, never a silently dropped write.

    The flush is asserted at several delays after the control write because
    the read/write phases are one cycle apart; every delay must still reach a
    terminal status.
    """
    agent = icache_agent
    vaddr = 0xE400
    for delay in range(5):
        await agent.send(make_fetch(vaddr, 15))
        await agent.ctrl_write(ECC_IADDR, vaddr)
        await agent.begin_ecc_injection(ECC_TARGET_DATA, fencei_delay=delay)
        status = 0
        state = 0
        for _ in range(400):
            status = await agent.ctrl_read(ECC_CTRL)
            state = (status >> 4) & 0b111
            if state in (2, 7):
                break
        assert state in (2, 7), (
            f"delay {delay}: the injection did not reach a terminal status: "
            f"{status:#x}")
        await agent.ctrl_write(ECC_CTRL, ECC_ENABLE)
        await agent.fence_i()          # resynchronise the oracle with the flush
