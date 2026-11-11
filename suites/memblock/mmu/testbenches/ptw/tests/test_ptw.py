"""PTW standalone page-table walk tests."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.execution import execution
from suites.memblock.mmu.testbenches.l2tlb.env.l2tlb import PageMemory
from suites.memblock.mmu.testbenches.l2tlb.env.l2tlb import pte


async def _prepare(env, mode: int = 8, ppn: int = 0x80000, asid: int = 0) -> None:
    await env.reset()
    env.set_csr(satp_mode=mode, satp_asid=asid, satp_ppn=ppn)
    await env.edge()


def _root_leaf(env, vpn: int, ppn: int, **perms) -> None:
    perms = perms or dict(r=1, w=1, x=1, u=1, a=1, d=1)
    env.memory.write((0x80000 << 12) + ((vpn >> 18) & 0x1FF) * 8,
                     pte(ppn, **perms))


# PTW-01: 1GB leaf at level 2 (Sv39 root).
async def test_1g_leaf(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        _root_leaf(env, 0x12345, 0x40000)
        await env.issue(0x12345, source=1)
        resp = await env.wait_response(note="1g")
        assert resp["valid"] == 1
        assert resp["source"] == 1
        assert resp["s2xlate"] == 0
        assert resp["0_v"] == 1 and resp["0_pf"] == 0 and resp["0_af"] == 0
        assert resp["0_level"] == 2
        assert resp["0_ppn"] == (0x40000 >> 3)
        assert resp["0_tag"] == (0x12345 >> 3)
        assert resp["0_asid"] == 0
        assert [r.address for r in env.requests] == [0x80000000]
        assert resp["pteidx"] == [0, 0, 0, 0, 0, 1, 0, 0]
        if env.coverage:
            env.coverage.sample("walk", "1g")


# PTW-02: 2MB leaf at level 1 after a root non-leaf PTE.
async def test_2m_leaf(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x80000, 0x12345, 0x4000, level=1, mid_ppn=0x80001)
        await env.issue(0x12345)
        resp = await env.wait_response(note="2m")
        assert resp["0_v"] == 1 and resp["0_level"] == 1
        assert resp["0_ppn"] == (0x4000 >> 3)
        assert resp["0_pf"] == 0 and resp["0_af"] == 0
        assert len(env.requests) == 2
        assert env.requests[0].address == 0x80000000
        assert env.requests[1].address == (0x80001 << 12) + ((0x12345 >> 9) & 0x1FF) * 8
        if env.coverage:
            env.coverage.sample("walk", "2m")


# PTW-03: a 4KB walk hands the final level to LLPTW and ends PTW's part.
async def test_4k_hands_to_llptw(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x80000, 0x12345, 0xABC)
        await env.issue(0x12345, source=2)
        resp = await env.wait_response(note="4k llptw")
        assert resp is None
        assert env.llptw_requests
        ll = env.llptw_requests[0]
        assert ll["vpn"] == 0x12345
        assert ll["source"] == 2
        assert ll["s2xlate"] == 0
        assert len(env.requests) == 2
        if env.coverage:
            env.coverage.sample("llptw", "4k")


# PTW-04: invalid root PTE reports a page fault.
async def test_invalid_root_pte_fault(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.write((0x80000 << 12) + ((0x23456 >> 18) & 0x1FF) * 8,
                         pte(0, v=0, a=0, d=0))
        await env.issue(0x23456)
        resp = await env.wait_response(note="invalid root")
        assert resp["0_v"] == 0 and resp["0_pf"] == 1
        assert resp["0_af"] == 0
        if env.coverage:
            env.coverage.sample("fault", "fault")


# PTW-05: a PBMT leaf without mPBMTE faults.
async def test_pbmt_without_enable_fault(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        _root_leaf(env, 0x34567, 0x40000, pbmt=1)
        await env.issue(0x34567)
        resp = await env.wait_response(note="pbmt fault")
        assert resp["0_pf"] == 1 and resp["0_af"] == 0
        if env.coverage:
            env.coverage.sample("fault", "fault")


# PTW-06: a leaf whose PPN has high bits set reports an access fault.
async def test_ppn_high_access_fault(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        _root_leaf(env, 0x45678, 1 << 36)
        await env.issue(0x45678)
        resp = await env.wait_response(note="ppn af")
        assert resp["0_af"] == 1
        if env.coverage:
            env.coverage.sample("fault", "fault")


# PTW-07: PMP denial returns an access fault without issuing a memory read.
async def test_pmp_denied(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        _root_leaf(env, 0x56789, 0x40000)
        env.set_pmp(ld=1)
        await env.issue(0x56789)
        resp = await env.wait_response(note="pmp denied")
        assert resp["0_af"] == 1
        assert resp["0_v"] == 0
        assert env.requests == []
        if env.coverage:
            env.coverage.sample("fault", "fault")


# PTW-08: l2Hit uses req.ppn as the level-1 table base and reads once.
async def test_l2_hit_hint(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x80000, 0x12345, 0x4000, level=1, mid_ppn=0x80010)
        await env.issue(0x12345, l2hit=1, ppn=0x80010)
        resp = await env.wait_response(note="l2hit")
        assert resp["0_v"] == 1 and resp["0_level"] == 1
        assert resp["0_ppn"] == (0x4000 >> 3)
        assert len(env.requests) == 1
        assert env.requests[0].address == (0x80010 << 12) + ((0x12345 >> 9) & 0x1FF) * 8
        if env.coverage:
            env.coverage.sample("hit", "2m", "l2")


# PTW-09: Sv48 l3Hit starts at level 2 with req.ppn as the table base.
async def test_l3_hit_hint_sv48(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env, mode=9)
        env.memory.write((0x80020 << 12) + ((0x12345 >> 18) & 0x1FF) * 8,
                         pte(0x40000, r=1, w=1, x=1, u=1, a=1, d=1))
        await env.issue(0x12345, l3hit=1, ppn=0x80020)
        resp = await env.wait_response(note="l3hit")
        assert resp["0_v"] == 1 and resp["0_level"] == 2
        assert resp["0_ppn"] == (0x40000 >> 3)
        assert len(env.requests) == 1
        assert env.requests[0].address == (0x80020 << 12) + ((0x12345 >> 18) & 0x1FF) * 8
        if env.coverage:
            env.coverage.sample("hit", "1g", "l3")


# PTW-10: sfence in the middle of a walk aborts it; a later request succeeds.
async def test_sfence_mid_walk(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x80000, 0x6A000, 0xABC)
        await env.issue(0x6A000)
        await env.service(5)
        await env.pulse_sfence(hold=3, settle=3, service=True)
        env.clear_llptw_requests()
        env.clear_requests()
        env.memory.build_sv39(0x80000, 0x6A000, 0xABC)
        await env.issue(0x6A000)
        resp = await env.wait_response(note="after sfence")
        assert resp is None, "4KB walk must hand off to LLPTW, not return an unchecked PTW response"
        assert len(env.llptw_requests) == 1, env.llptw_requests
        assert env.llptw_requests[0]["vpn"] == 0x6A000
        assert env.llptw_requests[0]["s2xlate"] == 0
        if env.coverage:
            env.coverage.sample("sfence", "4k")


# PTW-11: the response is held stable under backpressure.
async def test_response_backpressure(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        _root_leaf(env, 0x7B000, 0x40000)
        await env.issue(0x7B000)
        while not env.response_valid():
            await env.service(1)
        snap = env.response_snapshot()
        for _ in range(15):
            await env.edge()
            assert env.response_snapshot() == snap
        env.set_resp_ready(1)
        await env.edge()
        assert env.response_valid() == 0


# PTW-12: bitmap check is issued for a non-stage2 leaf and its cf is reported.
async def test_bitmap_check(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        _root_leaf(env, 0x8C000, 0x40000)
        env.set_csr(bme=1, cmode=0)
        await env.edge()
        await env.issue(0x8C000)
        resp = await env.wait_response(note="bitmap")
        assert resp["0_v"] == 1 and resp["0_cf"] == 0
        assert env.bitmap_requests
        req = env.bitmap_requests[0]
        assert req["level"] == 2
        assert req["s2xlate"] == 0
        env.coverage.sample("bitmap", "1g") if env.coverage else None


# PTW-13: bitmap check failure is carried in the response cf bit.
async def test_bitmap_failure_flag(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        _root_leaf(env, 0x9D000, 0x40000)
        env.set_csr(bme=1, cmode=0)
        env.set_bitmap_cf(1)
        await env.edge()
        await env.issue(0x9D000)
        resp = await env.wait_response(note="bitmap fail")
        assert resp["0_v"] == 1
        assert resp["0_cf"] == 1
        if env.coverage:
            env.coverage.sample("bitmap", "1g")


# PTW-14: onlyStage2 asks HPTW to translate the GPA and then walks G-stage.
async def test_only_stage2(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.set_csr(hgatp_mode=8, hgatp_vmid=5)
        # HPTW returns an identity 1GB mapping for the GPA page tables.
        env.queue_hptw_response(resp_gpf=0, resp_gaf=0, resp_tag=0x12345,
                                resp_vmid=5, resp_ppn=0x40000, resp_level=2,
                                resp_perm_r=1, resp_perm_w=1, resp_perm_x=1,
                                resp_perm_a=1, resp_perm_d=1)
        env.memory.write((0x40000 << 12) + ((0x12345 >> 18) & 0x1FF) * 8,
                         pte(0x90000, r=1, w=1, x=1, u=1, a=1, d=1))
        await env.issue(0x12345, s2xlate=2)
        resp = await env.wait_response(note="onlyS2")
        assert resp["s2xlate"] == 2
        assert resp["h_gpf"] == 0 and resp["h_gaf"] == 0
        assert resp["h_ppn"] == 0x40000
        assert resp["h_level"] == 2
        assert resp["h_vmid"] == 5
        assert env.hptw_requests
        if env.coverage:
            env.coverage.sample("hptw", "1g")


# PTW-15: stage1Hit returns the merged stage-1 response after the last HPTW
# translation of the GPA, without walking the VS page tables again.
async def test_stage1_hit_merge(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.set_csr(vsatp_mode=8, vsatp_asid=1, vsatp_ppn=0x80010,
                    hgatp_mode=8, hgatp_vmid=7)
        env.preload_stage1_hit(tag=0x6000, asid=1, vmid=7, level=0, v=1,
                              ppn=0xABC >> 3, ppn_low=0xABC & 7,
                              pteidx=1, perm_r=1, perm_w=1, perm_x=1,
                              perm_u=1, perm_a=1, perm_d=1)
        env.queue_hptw_response(resp_gpf=0, resp_gaf=0, resp_tag=0x30000,
                                resp_vmid=7, resp_ppn=0x90000, resp_level=0,
                                resp_perm_r=1, resp_perm_w=1, resp_perm_x=1,
                                resp_perm_a=1, resp_perm_d=1)
        await env.issue(0x30000, s2xlate=3, stage1hit=1)
        resp = await env.wait_response(note="stage1 merge")
        assert resp["s2xlate"] == 3
        assert resp["0_tag"] == 0x6000
        assert resp["0_tag"] == 0x6000 and resp["0_ppn"] == (0xABC >> 3)
        assert resp["0_level"] == 0 and resp["0_v"] == 1
        assert env.hptw_requests and env.requests == []
        if env.coverage:
            env.coverage.sample("stage1", "4k", "stage1")


# PTW-16: Sv48 512GB leaf at level 3.
async def test_sv48_512g_leaf(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env, mode=9)
        vpn = 0x1234567
        final = 1 << 27
        env.memory.write((0x80000 << 12) + ((vpn >> 27) & 0x1FF) * 8,
                         pte(final, r=1, w=1, x=1, u=1, a=1, d=1))
        await env.issue(vpn)
        resp = await env.wait_response(note="512g")
        assert resp["0_v"] == 1 and resp["0_level"] == 3
        assert resp["0_ppn"] == (final >> 3)
        if env.coverage:
            env.coverage.sample("walk", "1g")


# PTW-17: sfence in the middle of a 2MB walk; the retried request succeeds.
async def test_sfence_mid_2m_walk(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x80000, 0x6C000, 0x4000, level=1, mid_ppn=0x80001)
        await env.issue(0x6C000)
        await env.service(4)
        await env.pulse_sfence(hold=3, settle=3, service=True)
        env.clear_pending_memory()
        env.clear_requests()
        await env.issue(0x6C000)
        resp = await env.wait_response(note="2m after sfence")
        assert resp["0_v"] == 1 and resp["0_level"] == 1
        assert resp["0_ppn"] == (0x4000 >> 3)
        if env.coverage:
            env.coverage.sample("sfence", "2m")


# PTW-18: LLPTW valid holds while its ready is low.
async def test_llptw_backpressure(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x80000, 0x6E000, 0xABC)
        env.set_llptw_ready(0)
        await env.issue(0x6E000, source=3)
        for _ in range(20):
            await env.service(1)
            if env.llptw_valid():
                break
        assert env.llptw_valid() == 1
        snap = env.llptw_snapshot()
        for _ in range(10):
            await env.edge()
            assert env.llptw_valid() == 1
            assert env.llptw_snapshot() == snap
        env.set_llptw_ready(1)
        await env.edge()
        assert env.llptw_valid() == 0


# PTW-19: the request port is not ready while a walk is active.
async def test_request_while_busy(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x80000, 0x70000, 0x4000, level=1)
        await env.issue(0x70000)
        for _ in range(5):
            await env.service(1)
            if not env.request_ready():
                break
        assert env.request_ready() == 0
        # Finish the first walk, then a second request is accepted.
        resp = await env.wait_response(note="busy")
        assert resp["0_v"] == 1
        assert env.request_ready() == 1


# PTW-20: io_mem_mask stalls the walk until it is cleared.
async def test_mem_mask_stall(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        _root_leaf(env, 0x72000, 0x40000)
        env.set_mem_mask(1)
        await env.issue(0x72000)
        for _ in range(20):
            await env.service(1)
        assert env.requests == []
        await env.pulse_sfence(hold=2, settle=0, service=True)
        env.set_mem_mask(0)
        await env.service(2)
        await env.issue(0x72000)
        resp = await env.wait_response(note="after mask")
        assert resp["0_v"] == 1
        if env.coverage:
            env.coverage.sample("walk", "1g")


# PTW-21: satp.changed flushes and a new root produces a new translation.
async def test_satp_changed_rewalk(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        _root_leaf(env, 0x74000, 0x40000)
        await env.issue(0x74000)
        first = await env.wait_response(note="old satp")
        assert first["0_ppn"] == (0x40000 >> 3)
        env.set_csr(satp_ppn=0x84000, satp_changed=1)
        await env.edge()
        env.set_csr(satp_changed=0)
        await env.service(3)
        env.memory.write((0x84000 << 12) + ((0x74000 >> 18) & 0x1FF) * 8,
                         pte(0x80000, r=1, w=1, x=1, u=1, a=1, d=1))
        await env.issue(0x74000)
        second = await env.wait_response(note="new satp")
        assert second["0_ppn"] == (0x80000 >> 3)


# PTW-22: PMP mmio denial also produces an access fault.
async def test_pmp_mmio_fault(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        _root_leaf(env, 0x76000, 0x40000)
        env.set_pmp(mmio=1)
        await env.issue(0x76000)
        resp = await env.wait_response(note="pmp mmio")
        assert resp["0_af"] == 1
        assert env.requests == []


# PTW-23: vsatp/hgatp/virt changed sources each flush the FSM.
async def test_csr_change_sources(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        for key in ("vsatp_changed", "hgatp_changed", "virt_changed"):
            _root_leaf(env, 0x78000, 0x40000)
            await env.issue(0x78000)
            assert (await env.wait_response(note=key))["0_v"] == 1
            await env.pulse_csr_change(key)
            await env.service(3)
            assert env.request_ready() == 1


# PTW-24: jmp_bitmap_check uses the cached PTE and skips the page-table read.
async def test_bitmap_cached_pte(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.set_csr(bme=1, cmode=0)
        await env.edge()
        leaf = pte(0x40000, r=1, w=1, x=1, u=1, a=1, d=1)
        await env.issue(0x8E000, jmp_bitmap=1, bitmap_pte=leaf,
                        bitmap_splevel=2)
        resp = await env.wait_response(note="bitmap cached")
        assert resp["0_v"] == 1 and resp["0_level"] == 2
        assert resp["0_ppn"] == (0x40000 >> 3)
        assert env.requests == []
        assert env.bitmap_requests
        if env.coverage:
            env.coverage.sample("bitmap", "1g")


# PTW-25: HPTW guest page fault is forwarded on the h_resp channel.
async def test_only_stage2_gpf(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.set_csr(hgatp_mode=8, hgatp_vmid=5)
        env.queue_hptw_response(resp_gpf=1, resp_gaf=0)
        await env.issue(0x12345, s2xlate=2)
        resp = await env.wait_response(note="onlyS2 gpf")
        assert resp["h_gpf"] == 1 and resp["h_gaf"] == 0
        assert env.requests == []
        if env.coverage:
            env.coverage.sample("fault", "fault")


# PTW-26: HPTW access fault is forwarded on the h_resp channel.
async def test_only_stage2_gaf(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.set_csr(hgatp_mode=8, hgatp_vmid=5)
        env.queue_hptw_response(resp_gpf=0, resp_gaf=1)
        await env.issue(0x12345, s2xlate=2)
        resp = await env.wait_response(note="onlyS2 gaf")
        assert resp["h_gaf"] == 1
        if env.coverage:
            env.coverage.sample("fault", "fault")


# PTW-27: an allStage VS page-table access is an implicit G-stage load, so its
# G-stage PTE must be readable (R=1). Execute-only (R=0,X=1) is not enough:
# RISC-V privileged v20260120 hypervisor 14.1.5.1 checks these accesses as
# implicit loads and the priv-preface limits MXR to explicit memory accesses.
# The legal readable control is test_normal_all_stage_identity_hptw.
async def test_all_stage_implicit_gstage_read_requires_r(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        capability = env.mxr_input_capability
        if capability.driveable:
            # Legacy schema exposes the pin: drive the dangerous value so the
            # old RTL defect is visible.
            env.set_csr(mxr=1)
        else:
            # Current schema trims MXR. Functional code only reads the public
            # capability and checks the fail-closed contract; no live pin or
            # CSR dictionary is touched.
            assert capability.reason
            with pytest.raises(ValueError, match="requires R=1"):
                env.set_csr(mxr=1)
        env.set_csr(vsatp_mode=8, vsatp_asid=1, vsatp_ppn=0x80010,
                    hgatp_mode=8, hgatp_vmid=7)
        env.queue_hptw_response(
            resp_gpf=0, resp_gaf=0, resp_tag=0x80010, resp_vmid=7,
            resp_ppn=0x80010, resp_level=0, resp_n=0, resp_pbmt=0,
            resp_perm_r=0, resp_perm_w=0, resp_perm_x=1,
            resp_perm_a=1, resp_perm_d=0)
        await env.issue(0x30000, s2xlate=3, stage1hit=0)
        resp = await env.wait_response(note="implicit gstage execute-only")
        assert resp is not None
        assert resp["h_gpf"] == 1 and resp["h_gaf"] == 0, resp
        assert env.requests == [], env.requests
        if env.coverage:
            env.coverage.sample("fault", "fault")


# PTW-28: allStage with a GPA above the Sv39x4 range reports a guest fault
# before any page-table read.
async def test_allstage_gpa_high_fault(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.set_csr(vsatp_mode=8, vsatp_ppn=1 << 40, hgatp_mode=8, hgatp_vmid=5)
        await env.edge()
        await env.issue(0x12345, s2xlate=3)
        resp = await env.wait_response(note="allstage high")
        assert resp["h_gpf"] == 1
        if env.coverage:
            env.coverage.sample("fault", "fault")


# PTW-29: payload/CSR bit sweep through both all-ones and all-zeros.
@pytest.mark.structural_stress
async def test_bit_sweep(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        for endpoint in (1, 0):
            env.structural_input_sweep(endpoint)
            env.set_pmp(ld=0, mmio=0)
            env.drive_structural_hptw_resp(1 if endpoint else 0)
            env.drive_structural_bitmap_resp(1 if endpoint else 0, endpoint)
            await env.pulse_sfence(settle=0)
            env.drive_structural_hptw_resp(0)
            env.drive_structural_bitmap_resp(0)
            for _ in range(10):
                await env.edge()
        env.structural_input_sweep(0)
        await env.edge()
        await _prepare(env)
        env.memory.write(0x80000000, pte(0x40000, r=1, w=1, x=1, u=1, a=1, d=1))
        await env.issue(0x12345)
        restored = await env.wait_response(note="after structural stress")
        assert restored is not None and restored["0_v"] == 1
        assert restored["0_pf"] == 0 and restored["0_af"] == 0
        assert restored["0_ppn"] == 0x40000 >> 3


# PTW-30: stage1Hit allStage with every S1 and G leaf level.  This drives the
# full_gvpn_reg reconstruction for level 0/1/2/3 and the NAPOT (n=1) level-0
# arm, then checks the merged stage-1/stage-2 response.
async def test_stage1_hit_full_gvpn_levels(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.set_csr(vsatp_mode=8, vsatp_asid=1, vsatp_ppn=0x80010,
                    hgatp_mode=8, hgatp_vmid=7)
        combos = [(s1, h, 0) for s1 in range(4) for h in range(4)]
        combos.append((0, 0, 1))
        for s1level, hlevel, napot in combos:
            vpn = 0x30000
            gpa = 0xABC000 + s1level * 0x1000
            env.preload_stage1_hit(tag=vpn >> 3, asid=1, vmid=7,
                                  level=s1level, v=1, n=napot,
                                  ppn=(gpa >> 3) >> 3, ppn_low=gpa & 7,
                                  pteidx=1, perm_r=1, perm_w=1, perm_x=1,
                                  perm_u=1, perm_a=1, perm_d=1)
            env.queue_hptw_response(
                resp_gpf=0, resp_gaf=0, resp_tag=gpa >> 3,
                resp_vmid=7, resp_ppn=0x90000 + s1level * 0x10,
                resp_level=hlevel, resp_n=0, resp_pbmt=0,
                resp_perm_r=1, resp_perm_w=1, resp_perm_x=1,
                resp_perm_a=1, resp_perm_d=1)
            await env.issue(vpn, s2xlate=3, stage1hit=1)
            resp = await env.wait_response(
                note=f"full gvpn s1={s1level} s2={hlevel} n={napot}")
            assert resp is not None, (s1level, hlevel, napot)
            assert resp["0_v"] == 1, (s1level, hlevel, napot, resp)
            assert resp["0_level"] == s1level, (s1level, hlevel, resp)
            assert resp["0_n"] == napot, (s1level, hlevel, napot, resp)
            assert resp["h_level"] == hlevel, (s1level, hlevel, resp)
        assert len(env.hptw_requests) >= len(combos), env.hptw_requests
        # G-stage page fault on the stage1Hit path records hptw_resp_gpf.
        env.preload_stage1_hit(n=0)
        env.queue_hptw_response(
            resp_gpf=1, resp_gaf=0, resp_tag=0xABC, resp_vmid=7,
            resp_ppn=0x90000, resp_level=0, resp_n=0, resp_pbmt=0,
            resp_perm_r=0, resp_perm_w=0, resp_perm_x=0,
            resp_perm_a=0, resp_perm_d=0)
        await env.issue(0x30000, s2xlate=3, stage1hit=1)
        fault = await env.wait_response(note="stage1hit gpf")
        assert fault is not None and fault["h_gpf"] == 1, fault


# PTW-31: normal (non-stage1Hit) allStage 2MB leaf walk.  The VS page-table
# GPAs are identity-mapped by the HPTW, so the walk reads root and mid tables,
# asks HPTW for both page-table GPAs and the final GPA, and merges the result.
async def test_normal_all_stage_identity_hptw(ptw_env):
    env = ptw_env
    async with execution(env):
        await _prepare(env)
        env.set_csr(vsatp_mode=8, vsatp_asid=1, vsatp_ppn=0x80010,
                    hgatp_mode=8, hgatp_vmid=7)
        env.set_hptw_identity(True)
        vpn = 0x30000
        root_index = (vpn >> 18) & 0x1FF
        mid_index = (vpn >> 9) & 0x1FF
        env.memory.write(0x80010000 + root_index * 8,
                         pte(0x80011, r=0, w=0, x=0, u=0, a=0, d=0))
        env.memory.write(0x80011000 + mid_index * 8,
                         pte(0x40000, r=1, w=1, x=1, u=1, a=1, d=1))
        await env.issue(vpn, s2xlate=3, stage1hit=0)
        resp = await env.wait_response(note="normal allstage", max_cycles=400)
        assert resp is not None
        assert resp["valid"] == 1 and resp["s2xlate"] == 3, resp
        assert resp["0_v"] == 1 and resp["0_level"] == 1, resp
        assert resp["0_ppn"] == (0x40000 >> 3), resp
        assert resp["0_pf"] == 0 and resp["0_af"] == 0, resp
        assert resp["h_gpf"] == 0 and resp["h_gaf"] == 0, resp
        assert resp["h_ppn"] == 0x40000 and resp["h_level"] == 0, resp
        assert [req.address for req in env.requests] == [0x80010000, 0x80011C00], [
            hex(req.address) for req in env.requests]
        assert [req["gvpn"] for req in env.hptw_requests] == [
            0x80010, 0x80011, 0x40000], env.hptw_requests
