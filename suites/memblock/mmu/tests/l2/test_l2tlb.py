"""L2TLB top-level integration tests with a page-table memory responder."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.execution import execution, refresh
from suites.memblock.mmu.checks import check_l2_success
from tests.l2.soundness_helpers import check_address_fence_and_neighbor
from tests.l2.soundness_helpers import check_misaligned_1g_leaf


async def test_isa_misaligned_1g_leaf_is_page_fault(l2tlb_env):
    await check_misaligned_1g_leaf(l2tlb_env, _prepare)


async def test_address_fence_preserves_neighbor(l2tlb_env):
    await check_address_fence_and_neighbor(l2tlb_env, _prepare, _build)
from suites.memblock.mmu.l2.l2tlb import pte


def _setup(env, csr: dict | None = None) -> None:
    env.set_csr(**(csr or dict(satp_mode=8, satp_asid=0, satp_ppn=0x80000, imode=0)))


async def _prepare(env, csr: dict | None = None) -> None:
    await env.reset()
    _setup(env, csr)
    await env.write_csr(0x3B0, (1 << 46) - 1)
    await env.write_csr(0x3A0, 0x1F)
    await env.edge()


# L2TLB-WALK-01: a 1GB leaf at the root produces a real translation after one
# memory read, with the level and sector PPN selected by the walker.
async def test_1g_leaf_through_real_walk(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.start_walk(0x40000, leaf_at_root=True)
        await env.issue(0x12345, 0)
        resp = await env.wait_response(note="1g leaf")
        assert resp["valid"] == 1
        assert resp["s2xlate"] == 0
        assert resp["s1_v"] == 1, resp
        check_l2_success(resp)
        assert resp["s1_level"] == 2, resp
        assert resp["s1_ppn"] == (0x40000 >> 3), resp
        assert resp["s1_pf"] == 0 and resp["s1_af"] == 0, resp
        assert len(env.requests) == 1
        assert env.requests[0].address == (0x80000 << 12)
        if env.coverage is not None:
            env.coverage.sample("walk", "1g", 0)


# L2TLB-FAULT-01: an invalid root PTE produces a fake/fault response instead of
# a translation.
async def test_invalid_root_pte_reports_fault(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.start_walk(0x40000, leaf_at_root=False)
        env.walk_script = {6: [pte(0, v=0, a=0, d=0)]}
        env.walk_step = {6: 0}
        await env.issue(0x23456, 0)
        resp = await env.wait_response(note="invalid root")
        assert resp["valid"] == 1
        assert resp["s1_v"] == 0
        assert resp["s1_pf"] == 1
        if env.coverage is not None:
            env.coverage.sample("fault", "fault", 0)


# L2TLB-FAULT-02: a leaf with PBMT set while mPBMTE=0 must fault.
async def test_pbmt_without_enable_faults(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.start_walk(0x40000, leaf_at_root=True,
                       perms=dict(r=1, w=1, x=1, u=1, a=1, d=1, pbmt=3))
        await env.issue(0x34567, 0)
        resp = await env.wait_response(note="pbmt fault")
        assert resp["valid"] == 1
        assert resp["s1_pf"] == 1, resp
        if env.coverage is not None:
            env.coverage.sample("fault", "fault", 0)


# L2TLB-CACHE-01: repeating the same request completes without another walk
# once the PTE is resident in the PtwCache.
async def test_repeat_request_hits_pwt_cache(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.start_walk(0x40000, leaf_at_root=True)
        await env.issue(0x45678, 0)
        first = await env.wait_response(note="first walk")
        assert first["s1_v"] == 1 and first["s1_pf"] == 0
        check_l2_success(first)
        before = len(env.requests)
        await env.issue(0x45678, 0)
        second = await env.wait_response(note="repeat")
        assert second["s1_v"] == 1 and second["s1_pf"] == 0
        check_l2_success(second)
        assert second["s1_ppn"] == first["s1_ppn"]
        assert len(env.requests) == before, "cache hit must not read memory again"
        if env.coverage is not None:
            env.coverage.sample("cache_hit", "1g", 0)


# L2TLB-FENCE-01: sfence between the two requests forces a new walk.
async def test_sfence_forces_walk(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.start_walk(0x40000, leaf_at_root=True)
        await env.issue(0x56789, 0)
        assert (await env.wait_response(note="before fence"))["s1_v"] == 1
        env.sfence["valid"].Set(1)
        env.sfence["rs1"].Set(1)
        env.sfence["rs2"].Set(1)
        for _ in range(3):
            await env.edge()
        env.sfence["valid"].Set(0)
        for _ in range(10):
            await env.edge()
        env.walk_step = {6: 0}
        env.requests.clear()
        await env.issue(0x56789, 0)
        resp = await env.wait_response(note="after fence")
        assert resp["s1_v"] == 1
        check_l2_success(resp)
        assert len(env.requests) >= 1, "sfence must discard the cached walk"
        if env.coverage is not None:
            env.coverage.sample("sfence", "1g", 0)


# L2TLB-PORT-01: the second TLB port also completes a translation.
async def test_second_port_translation(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.start_walk(0x40000, leaf_at_root=True)
        await env.issue(0x6789A, 0, port=1)
        resp = await env.wait_response(note="port 1", port=1)
        assert resp["valid"] == 1
        assert resp["s1_v"] == 1
        check_l2_success(resp)
        assert resp["s1_ppn"] == (0x40000 >> 3)
        if env.coverage is not None:
            env.coverage.sample("walk", "1g", 1)


# L2TLB-WALK-02: a 4KB translation walks root, middle and leaf levels.
async def test_4k_page_through_level0_walk(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.start_walk(0xABC)
        await env.issue(0x12345, 0)
        resp = await env.wait_response(note="4k walk")
        assert resp["valid"] == 1
        assert resp["s1_v"] == 1, resp
        check_l2_success(resp)
        assert resp["s1_level"] == 0, resp
        assert resp["s1_ppn"] == (0xABC >> 3), resp
        assert resp["s1_pf"] == 0 and resp["s1_af"] == 0, resp
        if env.coverage is not None:
            env.coverage.sample("walk", "1g", 0)


# L2TLB-WALK-03: a 2MB leaf at level 1 also completes and reports level 1.
async def test_2m_page_through_level1_walk(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.start_walk(0x4000, leaf_at_root=False)
        env.walk_script = {6: [pte(0x80001, a=0, d=0), pte(0x4000, r=1, w=1, x=1, u=1, a=1, d=1)]}
        env.walk_step = {6: 0}
        env.leaf_word = pte(0x4000, r=1, w=1, x=1, u=1, a=1, d=1)
        await env.issue(0x23456, 0)
        resp = await env.wait_response(note="2m walk")
        assert resp["valid"] == 1
        assert resp["s1_v"] == 1, resp
        check_l2_success(resp)
        assert resp["s1_level"] == 1, resp
        assert resp["s1_ppn"] == (0x4000 >> 3), resp
        assert resp["s1_pf"] == 0 and resp["s1_af"] == 0, resp


# L2TLB-WALK-04: a page-table image laid out in the sparse memory (rather than
# the per-source script) also walks correctly end to end.
async def test_memory_image_4k_walk(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        env.memory.build_sv39(0x80000, 0x12345, 0xABC)
        await env.issue(0x12345, 0)
        resp = await env.wait_response(note="image walk")
        assert resp["valid"] == 1
        assert resp["s1_v"] == 1, resp
        check_l2_success(resp)
        assert resp["s1_level"] == 0, resp
        assert resp["s1_ppn"] == (0xABC >> 3), resp
        assert resp["s1_pf"] == 0 and resp["s1_af"] == 0, resp


def _build(env, vpn: int, ppn: int, mid: int = 0x80001, leaf: int = 0x80002,
           level: int = 0, **perms) -> None:
    env.memory.build_sv39(0x80000, vpn, ppn, level=level,
                          mid_ppn=mid, leaf_ppn=leaf, perms=perms or None)


# L2TLB-MULTI-01: two 4KB translations with different leaf tables coexist in
# the PtwCache and both return their own PPN.
async def test_two_4k_translations(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x12345, 0xABC, mid=0x80001, leaf=0x80002)
        _build(env, 0x12400, 0xDEF, mid=0x80001, leaf=0x80003)
        await env.issue(0x12345, 0)
        first = await env.wait_response(note="vpn A")
        assert first["s1_v"] == 1 and first["s1_ppn"] == (0xABC >> 3), first
        check_l2_success(first)
        await env.issue(0x12400, 0)
        second = await env.wait_response(note="vpn B")
        assert second["s1_v"] == 1 and second["s1_ppn"] == (0xDEF >> 3), second
        check_l2_success(second)


# L2TLB-MULTI-02: distinct root indexes fetch distinct root lines.
async def test_root_index_variants(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        cases = [(0x1000, 0x100), (0x4000000, 0x200)]
        for index, (vpn, ppn) in enumerate(cases):
            _build(env, vpn, ppn, mid=0x80010 + index, leaf=0x80020 + index)
        for vpn, ppn in cases:
            await env.issue(vpn, 0)
            resp = await env.wait_response(note=f"root index {vpn:#x}")
            assert resp["s1_v"] == 1 and resp["s1_ppn"] == (ppn >> 3), resp
            check_l2_success(resp)


# L2TLB-MULTI-03: a 2MB leaf with the required PPN alignment is returned at
# level 1 and the LLPTW path is exercised.
async def test_2m_leaf_memory_image(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x20000, 0x4000, level=1, mid=0x80005)
        await env.issue(0x20000, 0)
        resp = await env.wait_response(note="2m image")
        assert resp["valid"] == 1
        assert resp["s1_v"] == 1 and resp["s1_level"] == 1, resp
        check_l2_success(resp)
        assert resp["s1_ppn"] == (0x4000 >> 3), resp
        assert resp["s1_pf"] == 0 and resp["s1_af"] == 0, resp


# L2TLB-FAULT-03: misaligned 2MB superpage PPN must fault.
async def test_misaligned_2m_leaf_faults(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x22000, 0x4001, level=1, mid=0x80006)
        await env.issue(0x22000, 0)
        resp = await env.wait_response(note="misaligned 2m")
        assert resp["valid"] == 1 and resp["s1_pf"] == 1, resp


# L2TLB-FAULT-04: reserved PTE bits fault.
async def test_reserved_bits_fault(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x24000, 0xABC, mid=0x80007, leaf=0x80008)
        leaf_addr = (0x80008 << 12) + (0x24000 & 0x1FF) * 8
        env.memory.write(leaf_addr, (1 << 55) | pte(0xABC, r=1, w=1, x=1, u=1, a=1, d=1))
        await env.issue(0x24000, 0)
        resp = await env.wait_response(note="reserved fault")
        assert resp["valid"] == 1 and resp["s1_pf"] == 1, resp


# L2TLB-FAULT-05: denying PMP for the walk address must produce an access fault.
async def test_pmp_denied_access_fault(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        env.memory.build_sv39(0x80000, 0x26000, 0xABC)
        await env.write_csr(0x3A0, 0x00)
        await env.issue(0x26000, 0)
        resp = await env.wait_response(note="pmp denied")
        assert resp["valid"] == 1
        assert resp["s1_af"] == 1 and resp["s1_v"] == 0, resp


# L2TLB-PORT-02: both ports fire on an actual clock edge and complete.
async def test_two_ports_same_cycle(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x28000, 0x110, mid=0x80009, leaf=0x8000A)
        _build(env, 0x2A000, 0x220, mid=0x80009, leaf=0x8000B)
        env.resp["ready"].Set(0)
        for req, vpn in ((env.req, 0x28000), (env.req1, 0x2A000)):
            req["valid"].Set(1)
            req["vpn"].Set(vpn)
            req["s2xlate"].Set(0)
        accepted = [False, False]
        for _ in range(40):
            refresh(env)
            fires = [not accepted[i] and env.read(req["ready"])
                     for i, req in enumerate((env.req, env.req1))]
            await env.service_memory(1)
            for i, req in enumerate((env.req, env.req1)):
                if fires[i]:
                    accepted[i] = True
                    req["valid"].Set(0)
            if all(accepted):
                break
        assert all(accepted), accepted
        snaps = [await env.wait_response(port=i, note=f"concurrent port {i}")
                 for i in (0, 1)]
        for i, (snap, vpn, ppn) in enumerate(zip(snaps, (0x28000, 0x2A000), (0x110, 0x220))):
            assert snap["s1_tag"] == vpn >> 3, (i, snap)
            assert snap["s1_ppn"] == ppn >> 3, (i, snap)
            assert snap["s1_v"] == 1 and snap["s1_pf"] == 0 and snap["s1_af"] == 0, (i, snap)
            check_l2_success(snap)


# L2TLB-STAGE-01: only-stage-1 uses vsatp and returns the VS ASID.


# L2TLB-STAGE-02: only-stage-2 walks hgatp and returns an S2 entry.


# L2TLB-STAGE-03: all-stage translates a VS page table through an identity
# G-stage mapping, exercising HPTW in addition to PTW.


# L2TLB-PMP-01: programming the PMP CSR block (multiple entries and address
# widths) must not break a subsequent walk when an allow-all entry is kept.


# L2TLB-CACHE-02: many distinct 4KB translations fill the PtwCache and are
# all answered with their own PPNs.


# L2TLB-CACHE-03: a small resident working set is served without re-walking.


# L2TLB-BACKPRESSURE-01: the response is held stable while ready is low.


# L2TLB-FENCE-02: sfence in the middle of a walk drops it; a later request
# completes with a fresh walk.


# L2TLB-CSR-01: after satp.changed software executes sfence; the next request
# walks through the new root and returns the new translation.


# L2TLB-CACHE-04: two VPNs whose leaf PTEs share a 64-byte line hit in the
# page cache after the first walk.


# L2TLB-PMP-02: a TOR entry covering the page tables allows the walk.


# L2TLB-CSR-02: writing the PMA/PMP CSR address space exercises the decoder
# and must leave a working allow-all configuration.


# L2TLB-BITMAP-01: with BME=1 and CMODE=0 the walk consults the bitmap table
# through Bitmap/BitmapCache; an all-ones bitmap admits the translation.


# L2TLB-BITMAP-03: BCLEAR invalidates the bitmap cache and forces re-reads.


# L2TLB-LAT-01: delayed memory responses still complete a walk, and two
# requests can be in flight at once.


# L2TLB-FENCE-03: address-scoped sfence variants flush and re-walk.


# L2TLB-PMP-03: entries 16..31 and their configuration bytes are writable.


# L2TLB-BITMAP-04: multiple bitmap-checked walks fill Bitmap and BitmapCache
# entries across sets.


# L2TLB-STAGE-04: all-stage with bitmap enabled exercises the HPTW bitmap
# request source.


# L2TLB-MULTI-03: four independent 4KB translations can be outstanding at the
# same time with the response channel ready.  A non-zero memory latency is used
# Historical attribution superseded by verification-soundness-20261025.md.
# the walker has consumed the first; that is a harness timing artifact, not an
# Historical attribution superseded by verification-soundness-20261025.md.
@pytest.mark.parametrize("mem_latency", [0, 1, 7])
async def test_four_outstanding_translations(l2tlb_env, mem_latency):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        env.mem_latency = mem_latency
        cases = []
        for index in range(4):
            vpn = 0x70000 + index * 0x2000
            ppn = 0x4000 + index * 0x10
            _build(env, vpn, ppn, mid=0x80100, leaf=0x80200 + index)
            cases.append((vpn, ppn))
        env.resp["ready"].Set(1)
        for vpn, _ppn in cases:
            await env.issue(vpn, 0)
        seen = {}
        for _ in range(20000):
            if env.read(env.resp["valid"]):
                snap = {key: env.read(pin) for key, pin in env.resp.items()}
                check_l2_success(snap, stage=0)
                assert snap["s1_tag"] not in seen, ("duplicate response", snap)
                seen[snap["s1_tag"]] = snap["s1_ppn"]
            await env.service_memory(1)
            if len(seen) == len(cases):
                break
        assert len(seen) == len(cases), (len(seen), env.requests)
        for vpn, ppn in cases:
            assert seen.get(vpn >> 3) == (ppn >> 3), (hex(vpn), seen)


# L2TLB-STAGE-01: only-stage-1 uses vsatp and returns the VS ASID.
async def test_only_stage1_uses_vsatp(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env, dict(satp_mode=8, satp_asid=0, satp_ppn=0x80000,
                                 vsatp_mode=8, vsatp_asid=2, vsatp_ppn=0x81000,
                                 imode=0))
        env.walk_script = None
        env.memory.build_sv39(0x81000, 0x12345, 0xABC, mid_ppn=0x81001,
                              leaf_ppn=0x81002)
        await env.issue(0x12345, 1)
        resp = await env.wait_response(note="only stage1")
        assert resp["s2xlate"] == 1
        assert resp["s1_v"] == 1 and resp["s1_pf"] == 0, resp
        check_l2_success(resp)
        assert resp["s1_asid"] == 2, resp
        assert resp["s1_ppn"] == (0xABC >> 3), resp
        if env.coverage is not None:
            env.coverage.sample("walk", "1g", 0)


# L2TLB-STAGE-02: only-stage-2 walks hgatp and returns an S2 entry.
async def test_only_stage2_uses_hgatp(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env, dict(satp_mode=8, satp_asid=0, satp_ppn=0x80000,
                                 hgatp_mode=8, hgatp_vmid=5, hgatp_ppn=0x82000,
                                 imode=0))
        env.walk_script = None
        env.memory.build_sv39(0x82000, 0x30000, 0x90000, mid_ppn=0x82001,
                              leaf_ppn=0x82002)
        await env.issue(0x30000, 2)
        resp = await env.wait_response(note="only stage2")
        assert resp["s2xlate"] == 2
        assert resp["s2_gpf"] == 0 and resp["s2_gaf"] == 0, resp
        assert resp["s2_ppn"] == 0x90000, resp
        assert resp["s2_vmid"] == 5, resp
        if env.coverage is not None:
            env.coverage.sample("walk", "1g", 0)


# L2TLB-STAGE-03: all-stage translates a VS page table through an identity
# G-stage mapping, exercising HPTW in addition to PTW.
async def test_all_stage_identity_gstage(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env, dict(satp_mode=8, satp_asid=0, satp_ppn=0x80000,
                                 vsatp_mode=8, vsatp_asid=1, vsatp_ppn=0x80010,
                                 hgatp_mode=8, hgatp_vmid=7, hgatp_ppn=0x82000,
                                 imode=0))
        env.walk_script = None
        # G-stage identity 1GB leaf for GPA 0x80000000..0xBFFFFFFF.
        env.memory.write((0x82000 << 12) + ((0x80000000 >> 30) & 0x1FF) * 8,
                         pte(0x80000, r=1, w=1, x=1, u=1, a=1, d=1))
        # VS tables live at GPA 0x80010000/0x80011000/0x80012000.
        env.memory.build_sv39(0x80010, 0x30000, 0x80020, mid_ppn=0x80011,
                              leaf_ppn=0x80012)
        await env.issue(0x30000, 3)
        resp = await env.wait_response(note="all stage")
        assert resp["s2xlate"] == 3
        assert resp["s1_v"] == 1 and resp["s1_pf"] == 0, resp
        check_l2_success(resp)
        assert resp["s1_ppn"] == (0x80020 >> 3), resp
        assert resp["s2_gpf"] == 0 and resp["s2_gaf"] == 0, resp
        if env.coverage is not None:
            env.coverage.sample("walk", "1g", 0)


# L2TLB-PMP-01: programming the PMP CSR block (multiple entries and address
# widths) must not break a subsequent walk when an allow-all entry is kept.
async def test_pmp_configuration_sweep(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        for index in range(16):
            await env.write_csr(0x3B0 + index, (index + 1) << 20)
        await env.write_csr(0x3A0, 0x00000000)
        await env.write_csr(0x3A2, 0x00000000)
        await env.write_csr(0x3B0, (1 << 46) - 1)
        await env.write_csr(0x3A0, 0x1F)
        env.walk_script = None
        env.memory.build_sv39(0x80000, 0x3A000, 0xABC)
        await env.issue(0x3A000, 0)
        resp = await env.wait_response(note="after PMP sweep")
        assert resp["s1_v"] == 1 and resp["s1_pf"] == 0, resp
        check_l2_success(resp)


# L2TLB-CACHE-02: many distinct 4KB translations fill the PtwCache and are
# all answered with their own PPNs.
async def test_many_translations(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        cases = []
        for index in range(12):
            vpn = 0x10000 + index * 0x2000
            ppn = 0x1000 + index * 0x10
            leaf = 0x80050 + index
            _build(env, vpn, ppn, mid=0x80030, leaf=leaf)
            cases.append((vpn, ppn))
        for vpn, ppn in cases:
            await env.issue(vpn, 0)
            resp = await env.wait_response(note=f"many {vpn:#x}")
            assert resp["s1_v"] == 1 and resp["s1_pf"] == 0, (vpn, resp)
            check_l2_success(resp)
            assert resp["s1_ppn"] == (ppn >> 3), (vpn, resp)
        # Replay all of them: the cache must hold every translation.
        for vpn, ppn in cases:
            await env.issue(vpn, 0)
            resp = await env.wait_response(note=f"replay {vpn:#x}")
            assert resp["s1_v"] == 1 and resp["s1_ppn"] == (ppn >> 3), (vpn, resp)
            check_l2_success(resp)


# L2TLB-CACHE-03: a small resident working set is served without re-walking.
async def test_cache_resident_replays(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        cases = []
        for index in range(4):
            vpn = 0xC0000 + index * 0x2000
            ppn = 0x2000 + index * 0x10
            _build(env, vpn, ppn, mid=0x80070, leaf=0x80080 + index)
            cases.append((vpn, ppn))
        for vpn, ppn in cases:
            await env.issue(vpn, 0)
            resp = await env.wait_response(note=f"resident fill {vpn:#x}")
            assert resp["s1_v"] == 1 and resp["s1_ppn"] == (ppn >> 3), (vpn, resp)
            check_l2_success(resp)
        before_ptw = sum(1 for req in env.requests if req.source == 6)
        for vpn, ppn in cases:
            await env.issue(vpn, 0)
            resp = await env.wait_response(note=f"resident replay {vpn:#x}")
            assert resp["s1_v"] == 1 and resp["s1_ppn"] == (ppn >> 3), (vpn, resp)
            check_l2_success(resp)
        after_ptw = sum(1 for req in env.requests if req.source == 6)
        assert after_ptw == before_ptw, (before_ptw, after_ptw)


# L2TLB-BACKPRESSURE-01: the response is held stable while ready is low.
async def test_response_backpressure(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x50000, 0xABC, mid=0x80040, leaf=0x80041)
        env.resp["ready"].Set(0)
        await env.issue(0x50000, 0)
        while not env.read(env.resp["valid"]):
            await env.service_memory(1)
        snap = {key: env.read(signal) for key, signal in env.resp.items()}
        assert snap["s1_v"] == 1 and snap["s1_ppn"] == (0xABC >> 3), snap
        check_l2_success(snap)
        for _ in range(20):
            await env.edge()
            for key, signal in env.resp.items():
                assert env.read(signal) == snap[key], key
        env.resp["ready"].Set(1)
        await env.edge()
        assert env.read(env.resp["valid"]) == 0


# L2TLB-FENCE-02: sfence in the middle of a walk drops it; a later request
# completes with a fresh walk.
async def test_sfence_during_walk(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x52000, 0xABC, mid=0x80042, leaf=0x80043)
        await env.issue(0x52000, 0)
        for _ in range(10):
            await env.service_memory(1)
            if env.requests:
                break
        env.sfence["valid"].Set(1)
        env.sfence["rs1"].Set(1)
        env.sfence["rs2"].Set(1)
        for _ in range(3):
            await env.service_memory(1)
        env.sfence["valid"].Set(0)
        for _ in range(10):
            await env.service_memory(1)
        # A fresh request after the flush must still translate correctly.
        await env.issue(0x52000, 0)
        resp = await env.wait_response(note="after mid-walk sfence")
        assert resp["s1_v"] == 1 and resp["s1_ppn"] == (0xABC >> 3), resp
        check_l2_success(resp)


# L2TLB-CSR-01: after satp.changed software executes sfence; the next request
# walks through the new root and returns the new translation.
async def test_satp_change_with_sfence_rewalks(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x54000, 0xABC, mid=0x80044, leaf=0x80045)
        await env.issue(0x54000, 0)
        first = await env.wait_response(note="old satp")
        assert first["s1_v"] == 1 and first["s1_ppn"] == (0xABC >> 3), first
        check_l2_success(first)
        env.set_csr(satp_ppn=0x84000, satp_changed=1)
        env.sfence["valid"].Set(1)
        env.sfence["rs1"].Set(1)
        env.sfence["rs2"].Set(1)
        for _ in range(3):
            await env.edge()
        env.csr["satp_changed"].Set(0)
        env.sfence["valid"].Set(0)
        for _ in range(10):
            await env.edge()
        env.memory.build_sv39(0x84000, 0x54000, 0xDEF, mid_ppn=0x84001,
                              leaf_ppn=0x84002)
        await env.issue(0x54000, 0)
        second = await env.wait_response(note="new satp")
        assert second["s1_v"] == 1 and second["s1_ppn"] == (0xDEF >> 3), second
        check_l2_success(second)


# L2TLB-CACHE-04: two VPNs whose leaf PTEs share a 64-byte line hit in the
# page cache after the first walk.
async def test_shared_leaf_line_hits(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x56000, 0xABC, mid=0x80046, leaf=0x80047)
        _build(env, 0x56001, 0xDEF, mid=0x80046, leaf=0x80047)
        await env.issue(0x56000, 0)
        first = await env.wait_response(note="line fill")
        assert first["s1_v"] == 1 and first["s1_ppn"] == (0xABC >> 3), first
        check_l2_success(first)
        before_ptw = sum(1 for req in env.requests if req.source == 6)
        await env.issue(0x56001, 0)
        second = await env.wait_response(note="line hit")
        after_ptw = sum(1 for req in env.requests if req.source == 6)
        assert second["s1_v"] == 1 and second["s1_ppn"] == (0xDEF >> 3), second
        check_l2_success(second)
        assert after_ptw == before_ptw, (before_ptw, after_ptw)


# L2TLB-PMP-02: a TOR entry covering the page tables allows the walk.
async def test_pmp_tor_allow(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        # TOR: [0, pmpaddr0 << 2), RWX. Cover 0x00000000..0xBFFFFFFF.
        await env.write_csr(0x3A0, 0x00000000)
        await env.write_csr(0x3B0, (0xC0000000 >> 2))
        await env.write_csr(0x3A0, 0x0F)
        env.walk_script = None
        env.memory.build_sv39(0x80000, 0x58000, 0xABC)
        await env.issue(0x58000, 0)
        resp = await env.wait_response(note="TOR allow")
        assert resp["s1_v"] == 1 and resp["s1_pf"] == 0, resp
        check_l2_success(resp)


# L2TLB-CSR-02: writing the PMA/PMP CSR address space exercises the decoder
# and must leave a working allow-all configuration.
async def test_csr_decode_sweep(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        for addr in range(0x3A0, 0x3C0):
            await env.write_csr(addr, 0)
        await env.write_csr(0x3B0, (1 << 46) - 1)
        await env.write_csr(0x3A0, 0x1F)
        env.walk_script = None
        env.memory.build_sv39(0x80000, 0x5A000, 0xABC)
        await env.issue(0x5A000, 0)
        resp = await env.wait_response(note="after CSR sweep")
        assert resp["s1_v"] == 1 and resp["s1_pf"] == 0, resp
        check_l2_success(resp)


# L2TLB-BITMAP-01: with BME=1 and CMODE=0 the walk consults the bitmap table
# through Bitmap/BitmapCache; an all-ones bitmap admits the translation.
async def test_bitmap_enabled_walk(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x5C000, 0xABC, mid=0x80060, leaf=0x80061)
        # Bitmap base: BMA stores bits [57:6] of the machine address.
        for offset in range(0, 0x1000, 64):
            env.memory.write(0x90000000 + offset, 0, width=64)
        env.set_csr(bme=1, cmode=0, bma=(0x90000000 >> 6))
        await env.edge()
        await env.issue(0x5C000, 0)
        resp = await env.wait_response(note="bitmap enabled")
        check_l2_success(resp)
        assert resp["s1_v"] == 1 and resp["s1_pf"] == 0, resp
        assert any(req.source >= 0x8 for req in env.requests),\
            [(req.source, hex(req.address)) for req in env.requests]


# L2TLB-BITMAP-03: BCLEAR invalidates the bitmap cache and forces re-reads.
async def test_bitmap_clear(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x60000, 0xABC, mid=0x80064, leaf=0x80065)
        _build(env, 0x60001, 0xDEF, mid=0x80064, leaf=0x80065)
        for offset in range(0, 0x1000, 64):
            env.memory.write(0x90000000 + offset, 0, width=64)
        env.set_csr(bme=1, cmode=0, bma=(0x90000000 >> 6))
        await env.edge()
        await env.issue(0x60000, 0)
        assert (await env.wait_response(note="bitmap fill"))["s1_v"] == 1
        env.set_csr(bclear=1)
        await env.edge()
        env.set_csr(bclear=0)
        await env.edge()
        # A different VPN in the same PTE line still needs a bitmap lookup.
        await env.issue(0x60001, 0)
        resp = await env.wait_response(note="bitmap after clear")
        assert resp["s1_v"] == 1 and resp["s1_ppn"] == (0xDEF >> 3), resp
        check_l2_success(resp)


# L2TLB-LAT-01: delayed memory responses still complete a walk, and two
# requests can be in flight at once.
async def test_memory_latency_and_two_outstanding(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x62000, 0xABC, mid=0x80066, leaf=0x80067)
        _build(env, 0x64000, 0xDEF, mid=0x80066, leaf=0x80068)
        env.mem_latency = 7
        env.resp["ready"].Set(1)
        await env.issue(0x62000, 0)
        await env.issue(0x64000, 0)
        seen = {}
        for _ in range(4000):
            if env.read(env.resp["valid"]):
                snap = {key: env.read(pin) for key, pin in env.resp.items()}
                check_l2_success(snap, stage=0)
                tag = snap["s1_tag"]
                assert tag not in seen, ("duplicate response", snap)
                seen[tag] = snap["s1_ppn"]
            await env.service_memory(1)
            if len(seen) == 2:
                break
        assert seen.get(0x62000 >> 3) == (0xABC >> 3), seen
        assert seen.get(0x64000 >> 3) == (0xDEF >> 3), seen


# L2TLB-FENCE-03: address-scoped sfence variants flush and re-walk.
async def test_sfence_scoped_variants(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x66000, 0xABC, mid=0x80069, leaf=0x8006A)
        await env.issue(0x66000, 0)
        assert (await env.wait_response(note="scoped-fill"))["s1_v"] == 1
        for rs1, rs2, addr, asid in ((1, 0, 0x66000, 0), (1, 1, 0x66000, 0)):
            before = sum(1 for req in env.requests if req.source == 6)
            env.sfence["valid"].Set(1)
            env.sfence["rs1"].Set(rs1)
            env.sfence["rs2"].Set(rs2)
            env.sfence["addr"].Set(addr)
            env.sfence["id"].Set(asid)
            for _ in range(3):
                await env.edge()
            env.sfence["valid"].Set(0)
            for _ in range(8):
                await env.edge()
            await env.issue(0x66000, 0)
            resp = await env.wait_response(note=f"scoped-{rs1}{rs2}")
            assert resp["s1_v"] == 1 and resp["s1_ppn"] == (0xABC >> 3), resp
            check_l2_success(resp)
            after = sum(1 for req in env.requests if req.source == 6)
            assert after > before, (rs1, rs2, before, after)


# L2TLB-PMP-03: entries 16..31 and their configuration bytes are writable.
async def test_pmp_high_entries(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        for index in range(16):
            await env.write_csr(0x3C0 + index, (index + 1) << 22)
        await env.write_csr(0x3A2, 0x00000000)
        await env.write_csr(0x3A3, 0x00000000)
        await env.write_csr(0x3B0, (1 << 46) - 1)
        await env.write_csr(0x3A0, 0x1F)
        env.walk_script = None
        env.memory.build_sv39(0x80000, 0x68000, 0xABC)
        await env.issue(0x68000, 0)
        resp = await env.wait_response(note="high PMP entries")
        assert resp["s1_v"] == 1 and resp["s1_pf"] == 0, resp
        check_l2_success(resp)


# L2TLB-BITMAP-04: multiple bitmap-checked walks fill Bitmap and BitmapCache
# entries across sets.
async def test_bitmap_many_walks(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        for offset in range(0, 0x2000, 64):
            env.memory.write(0x90000000 + offset, 0, width=64)
        env.set_csr(bme=1, cmode=0, bma=(0x90000000 >> 6))
        cases = []
        for index in range(8):
            vpn = 0x70000 + index * 0x2000
            ppn = 0x3000 + index * 0x40
            _build(env, vpn, ppn, mid=0x80070, leaf=0x80090 + index)
            cases.append((vpn, ppn))
        for vpn, ppn in cases:
            await env.issue(vpn, 0)
            resp = await env.wait_response(note=f"bitmap many {vpn:#x}")
            check_l2_success(resp)
            assert resp["s1_v"] == 1 and resp["s1_ppn"] == (ppn >> 3), (vpn, resp)
        assert any(req.source >= 0x8 for req in env.requests)


# L2TLB-STAGE-04: all-stage with bitmap enabled exercises the HPTW bitmap
# request source.
async def test_all_stage_with_bitmap(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env, dict(satp_mode=8, satp_asid=0, satp_ppn=0x80000,
                                 vsatp_mode=8, vsatp_asid=1, vsatp_ppn=0x80010,
                                 hgatp_mode=8, hgatp_vmid=7, hgatp_ppn=0x82000,
                                 imode=0))
        env.walk_script = None
        for offset in range(0, 0x2000, 64):
            env.memory.write(0x90000000 + offset, 0, width=64)
        env.memory.write((0x82000 << 12) + ((0x80000000 >> 30) & 0x1FF) * 8,
                         pte(0x80000, r=1, w=1, x=1, u=1, a=1, d=1))
        env.memory.build_sv39(0x80010, 0x30000, 0x80020, mid_ppn=0x80011,
                              leaf_ppn=0x80012)
        env.set_csr(bme=1, cmode=0, bma=(0x90000000 >> 6))
        await env.edge()
        await env.issue(0x30000, 3)
        resp = await env.wait_response(note="all stage bitmap")
        check_l2_success(resp)
        assert resp["s2xlate"] == 3
        assert resp["s1_v"] == 1 and resp["s1_pf"] == 0, resp
        assert resp["s2_gpf"] == 0 and resp["s2_gaf"] == 0, resp


# L2TLB-BITMAP-04: the bitmap check uses cf=1 as failure.  A bitmap word with
# all bits set denies the translation (af), while an all-zero word allows it.
async def test_bitmap_deny_and_allow(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x5C000, 0xABC, mid=0x80060, leaf=0x80061)
        env.set_csr(bme=1, cmode=0, bma=(0x90000000 >> 6))
        # All ones -> cf=1 -> access fault.
        for offset in range(0, 0x2000, 64):
            env.memory.write(0x90000000 + offset, (1 << 512) - 1, width=64)
        await env.edge()
        await env.issue(0x5C000, 0)
        deny = await env.wait_response(note="bitmap deny")
        assert deny["s1_af"] == 1, deny
        # New DUT state: all zeros -> cf=0 -> translation succeeds.
        await _prepare(env)
        env.walk_script = None
        _build(env, 0x5C000, 0xABC, mid=0x80060, leaf=0x80061)
        for offset in range(0, 0x2000, 64):
            env.memory.write(0x90000000 + offset, 0, width=64)
        env.set_csr(bme=1, cmode=0, bma=(0x90000000 >> 6))
        await env.edge()
        await env.issue(0x5C000, 0)
        allow = await env.wait_response(note="bitmap allow")
        assert allow["s1_af"] == 0 and allow["s1_v"] == 1, allow
        check_l2_success(allow)
        assert allow["s1_ppn"] == (0xABC >> 3)
        if env.coverage:
            env.coverage.sample("walk", "4k", 0)


# Historical attribution superseded by verification-soundness-20261025.md.
# all cached translations.  After rewriting the leaf PTE from 0xABC to 0xDEF,
# the all-address sfence returns the old PPN with no new table read, while the
# same PTE rewrite followed by a scoped sfence re-walks and returns 0xDEF.
async def test_sfence_all_rewalks_after_pte_change(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        vpn = 0x77000
        _build(env, vpn, 0xABC, mid=0x80072, leaf=0x80073)
        await env.issue(vpn, 0)
        first = await env.wait_response(note="all-sfence fill")
        assert first["s1_ppn"] == (0xABC >> 3)
        env.memory.build_sv39(0x80000, vpn, 0xDEF,
                              mid_ppn=0x80072, leaf_ppn=0x80073)
        env.sfence["valid"].Set(1)
        env.sfence["rs1"].Set(1)
        env.sfence["rs2"].Set(1)
        for _ in range(3):
            await env.edge()
        env.sfence["valid"].Set(0)
        for _ in range(8):
            await env.edge()
        before = len(env.requests)
        await env.issue(vpn, 0)
        second = await env.wait_response(note="all-sfence query")
        assert second["s1_v"] == 1 and second["s1_pf"] == 0 and second["s1_af"] == 0, second
        check_l2_success(second)
        assert second["s1_ppn"] == (0xDEF >> 3), second
        assert len(env.requests) > before, "all-address sfence must re-walk"


# L2TLB-FENCE-05: the same PTE rewrite followed by a scoped sfence re-walks
# and returns the new PPN.  This is the positive counterpart of FENCE-04.
async def test_sfence_scoped_rewalks_after_pte_change(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _prepare(env)
        env.walk_script = None
        vpn = 0x78000
        _build(env, vpn, 0xABC, mid=0x80074, leaf=0x80075)
        await env.issue(vpn, 0)
        first = await env.wait_response(note="scoped fill")
        assert first["s1_ppn"] == (0xABC >> 3)
        env.memory.build_sv39(0x80000, vpn, 0xDEF,
                              mid_ppn=0x80074, leaf_ppn=0x80075)
        env.sfence["valid"].Set(1)
        env.sfence["rs1"].Set(0)
        env.sfence["rs2"].Set(1)
        env.sfence["addr"].Set(vpn << 12)
        env.sfence["id"].Set(0)
        for _ in range(3):
            await env.edge()
        env.sfence["valid"].Set(0)
        for _ in range(8):
            await env.edge()
        before = len(env.requests)
        await env.issue(vpn, 0)
        second = await env.wait_response(note="scoped query")
        assert second["s1_ppn"] == (0xDEF >> 3), second
        assert len(env.requests) > before


# L2TLB-PMA-02..04: PMA range 0x7C0..0x7C8 controls the attributes of page
# table memory.  A TOR entry covering the page tables is programmed through the
# distributed CSR path; the walk is allowed only when the entry is cacheable
# (C=1) and readable (R=1).  Non-cacheable or unreadable page tables raise an
# access fault before any table read.
def _pma_tor_cfg(entry1: int) -> int:
    values = [0x00, entry1, 0, 0, 0, 0, 0, 0]
    data = 0
    for index, value in enumerate(values):
        data |= value << (8 * index)
    return data


async def _pma_cover_page_tables(env, entry1_cfg: int) -> None:
    await _prepare(env)
    env.walk_script = None
    _build(env, 0x7A000, 0x456, mid=0x80076, leaf=0x80077)
    await env.write_csr(0x7C0, _pma_tor_cfg(entry1_cfg))
    await env.write_csr(0x7C8, 0)
    await env.write_csr(0x7C9, 0x3FFFFFFF)


async def test_pma_cacheable_page_tables_walk(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _pma_cover_page_tables(env, 0x4F)  # C=1, A=TOR, RWX
        await env.issue(0x7A000, 0)
        resp = await env.wait_response(note="pma cacheable")
        assert resp["s1_v"] == 1 and resp["s1_pf"] == 0, resp
        check_l2_success(resp)
        assert resp["s1_af"] == 0, resp
        assert resp["s1_ppn"] == (0x456 >> 3), resp
        assert [req.address for req in env.requests] == [
            0x80000000, 0x80076E80, 0x80077000], [
            hex(req.address) for req in env.requests]


async def test_pma_non_cacheable_page_tables_fault(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _pma_cover_page_tables(env, 0x0F)  # C=0, A=TOR, RWX
        await env.issue(0x7A000, 0)
        resp = await env.wait_response(note="pma non-cacheable")
        assert resp["s1_af"] == 1 and resp["s1_v"] == 0, resp
        assert env.requests == [], [hex(req.address) for req in env.requests]


async def test_pma_unreadable_page_tables_fault(l2tlb_env):
    env = l2tlb_env
    async with execution(env):
        await _pma_cover_page_tables(env, 0x4E)  # C=1, A=TOR, R=0
        await env.issue(0x7A000, 0)
        resp = await env.wait_response(note="pma unreadable")
        assert resp["s1_af"] == 1 and resp["s1_v"] == 0, resp
        assert env.requests == [], [hex(req.address) for req in env.requests]
