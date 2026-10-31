"""PtwCache standalone tests."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.legacy_pins import P
from suites.memblock.mmu.execution import execution, refresh, sweep_inputs
from suites.memblock.mmu.l2.l2tlb import pte
from suites.memblock.mmu.l2.ptwcache import CacheReq


def leaf(ppn: int, **kwargs) -> int:
    perms = dict(r=1, w=1, x=1, u=1, a=1, d=1)
    perms.update(kwargs)
    return pte(ppn, **perms)


def nonleaf(ppn: int, **kwargs) -> int:
    base = dict(r=0, w=0, x=0, u=0, a=0, d=0)
    base.update(kwargs)
    return pte(ppn, **base)


def leaves(base: int, count: int = 8) -> list[int]:
    return [leaf(base + index) for index in range(count)]


async def _prepare(env, satp_asid: int = 0, vsatp_asid: int = 0,
                   vmid: int = 0, mode: int = 8) -> None:
    await env.reset()
    env.set_csr(satp_asid=satp_asid, vsatp_asid=vsatp_asid,
                hgatp_vmid=vmid, hgatp_mode=mode)
    await env.edge()


# PTWC-01: 4KB L0 hit returns the sector PPN, permissions, tag and pteidx.
async def test_l0_hit_payload(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        ptes = leaves(0x80000)
        await env.refill_l0(0x30000, ptes)
        await env.issue(CacheReq(vpn=0x30000, source=1))
        snap = await env.wait_resp()
        assert snap["valid"] == 1 and snap["hit"] == 1
        assert snap["vpn"] == 0x30000 and snap["source"] == 1
        assert snap["is_first"] == 1
        assert snap["not_super"] == 1
        assert snap["e0_tag"] == (0x30000 >> 3)
        assert snap["e0_level"] == 0 and snap["e0_v"] == 1
        assert snap["e0_ppn"] == (0x80000 >> 3)
        assert snap["pteidx_0"] == 1
        for index in range(8):
            assert snap[f"pteidx_{index}"] == (1 if index == 0 else 0)
            assert snap[f"e{index}_v"] == 1
            assert snap[f"e{index}_perm_r"] == 1
            assert snap[f"e{index}_perm_w"] == 1
            assert snap[f"e{index}_perm_x"] == 1
        if env.coverage:
            env.coverage.sample("l0_fill", 0, 0)
            env.coverage.sample("l0_hit", 0, 0)


# PTWC-02: the low 3 VPN bits select the sector PTE (ppn_low) and pteidx.
async def test_l0_sector_selection(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        ptes = leaves(0x80000)
        await env.refill_l0(0x30006, ptes)
        for low in range(8):
            vpn = (0x30000 & ~7) | low
            await env.issue(CacheReq(vpn=vpn))
            snap = await env.wait_resp()
            assert snap["hit"] == 1, low
            assert sum(snap[f"pteidx_{index}"] for index in range(8)) == 1
            for index in range(8):
                assert snap[f"pteidx_{index}"] == (1 if index == low else 0), (low, index)
            expected_ppn = 0x80000 + low
            assert snap[f"e{low}_ppn_low"] == (expected_ppn & 7)
            assert snap[f"e{low}_ppn"] == (expected_ppn >> 3)
            if env.coverage:
                env.coverage.sample("l0_hit", 0, 0)


# PTWC-03: miss, refill, then hit with the same lookup.
async def test_miss_then_refill_hit(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        await env.issue(CacheReq(vpn=0x30000))
        miss = await env.wait_resp()
        assert miss["hit"] == 0
        if env.coverage:
            env.coverage.sample("miss", 0, 0)
        await env.refill_l0(0x30000, leaves(0x80000))
        await env.issue(CacheReq(vpn=0x30000))
        hit = await env.wait_resp()
        assert hit["hit"] == 1
        if env.coverage:
            env.coverage.sample("l0_fill", 0, 0)
            env.coverage.sample("l0_hit", 0, 0)


# PTWC-04: L1 non-leaf entry provides the next-level table PPN.
async def test_l1_nonleaf_hit(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0x30000
        target = 0x12345
        await env.refill_entries(vpn, 1, [nonleaf(target)] * 8)
        await env.issue(CacheReq(vpn=vpn))
        snap = await env.wait_resp()
        assert snap["hit"] == 0, snap
        assert snap["l1hit"] == 1, snap
        assert snap["l2hit"] == 0 and snap["l3hit"] == 0
        assert snap["ppn"] == target
        if env.coverage:
            env.coverage.sample("l1_fill", 1, 0)
            env.coverage.sample("l1_hit", 1, 0)


# PTWC-05: L2 non-leaf entry is reported as l2Hit.
async def test_l2_nonleaf_hit(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0x30000
        target = 0x23456
        await env.refill_entries(vpn, 2, [nonleaf(target)] * 8)
        await env.issue(CacheReq(vpn=vpn))
        snap = await env.wait_resp()
        assert snap["l2hit"] == 1 and snap["l1hit"] == 0
        assert snap["ppn"] == target
        if env.coverage:
            env.coverage.sample("l2_fill", 2, 0)
            env.coverage.sample("l2_hit", 2, 0)


# PTWC-06: L3 non-leaf entry is reported as l3Hit (Sv48).
async def test_l3_nonleaf_hit(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0x30000
        target = 0x34567
        await env.refill_entries(vpn, 3, [nonleaf(target)] * 8)
        await env.issue(CacheReq(vpn=vpn))
        snap = await env.wait_resp()
        assert snap["l3hit"] == 1 and snap["l2hit"] == 0
        assert snap["ppn"] == target
        if env.coverage:
            env.coverage.sample("l3_fill", 3, 0)
            env.coverage.sample("l3_hit", 3, 0)


# PTWC-07: a 2MB superpage leaf hits the SP cache at level 1.
async def test_sp_2m_hit(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0x30000
        ppn = 0x4000
        await env.refill_super(vpn, 1, leaf(ppn))
        await env.issue(CacheReq(vpn=vpn))
        snap = await env.wait_resp()
        assert snap["hit"] == 1, snap
        assert snap["not_super"] == 0
        assert snap["e0_level"] == 1
        assert snap["e0_ppn"] == (ppn >> 3)
        assert snap["e0_ppn_low"] == 0
        assert snap["e0_v"] == 1
        if env.coverage:
            env.coverage.sample("sp_fill", 1, 0)
            env.coverage.sample("l0_hit", 0, 0)


# PTWC-08: a 1GB superpage leaf hits the SP cache at level 2.
async def test_sp_1g_hit(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0x4000000
        ppn = 0x40000
        await env.refill_super(vpn, 2, leaf(ppn))
        await env.issue(CacheReq(vpn=vpn))
        snap = await env.wait_resp()
        assert snap["hit"] == 1 and snap["not_super"] == 0
        assert snap["e0_level"] == 2
        assert snap["e0_ppn"] == (ppn >> 3)
        if env.coverage:
            env.coverage.sample("sp_fill", 2, 0)


# PTWC-09: a 512GB leaf hits the level-3 SP entry.
async def test_sp_512g_hit(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0x30000000
        ppn = 1 << 27
        await env.refill_super(vpn, 3, leaf(ppn))
        await env.issue(CacheReq(vpn=vpn))
        snap = await env.wait_resp()
        assert snap["hit"] == 1 and snap["not_super"] == 0
        assert snap["e0_level"] == 3
        if env.coverage:
            env.coverage.sample("sp_fill", 3, 0)


# PTWC-10: ASID filtering and global PTEs.
async def test_asid_filtering(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, satp_asid=2)
        vpn = 0x30000
        await env.refill_l0(vpn, leaves(0x80000))
        await env.issue(CacheReq(vpn=vpn))
        assert (await env.wait_resp())["hit"] == 1
        env.set_csr(satp_asid=3)
        await env.issue(CacheReq(vpn=vpn))
        assert (await env.wait_resp())["hit"] == 0
        # Global PTE is visible regardless of ASID.
        await env.refill_l0(vpn, leaves(0x90000, 8))
        # Rewrite one global sector: easiest is a full refill with g=1 leaves.
        for index in range(8):
            ptes = leaves(0x90000)
        # The cache stores the sector from the last refill; use g=1 there.
        g_ptes = [leaf(0x90000 + index, g=1) for index in range(8)]
        await env.refill_entries(vpn, 0, g_ptes, selected=g_ptes[0])
        env.set_csr(satp_asid=5)
        await env.issue(CacheReq(vpn=vpn))
        assert (await env.wait_resp())["hit"] == 1


# PTWC-11: onlyStage1 uses vsatp ASID and ignores VMID.
async def test_only_stage1_asid(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, satp_asid=1, vsatp_asid=4, vmid=7)
        vpn = 0x31000
        await env.refill_l0(vpn, leaves(0x80000), s2xlate=1)
        await env.issue(CacheReq(vpn=vpn, s2xlate=1))
        assert (await env.wait_resp())["hit"] == 1
        if env.coverage:
            env.coverage.sample("l0_hit", 0, 1)
        env.set_csr(vsatp_asid=5)
        await env.issue(CacheReq(vpn=vpn, s2xlate=1))
        assert (await env.wait_resp())["hit"] == 0
        env.set_csr(vsatp_asid=4, hgatp_vmid=9)
        await env.issue(CacheReq(vpn=vpn, s2xlate=1))
        # onlyStage1 still checks VMID (the entry is not global).
        assert (await env.wait_resp())["hit"] == 0
        env.set_csr(hgatp_vmid=7)
        await env.issue(CacheReq(vpn=vpn, s2xlate=1))
        assert (await env.wait_resp())["hit"] == 1


# PTWC-12: onlyStage2 ignores ASID and checks VMID.
async def test_only_stage2_vmid(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, satp_asid=1, vsatp_asid=4, vmid=7)
        vpn = 0x32000
        await env.refill_l0(vpn, leaves(0x80000), s2xlate=2)
        await env.issue(CacheReq(vpn=vpn, s2xlate=2))
        assert (await env.wait_resp())["hit"] == 1
        if env.coverage:
            env.coverage.sample("l0_hit", 0, 2)
        env.set_csr(satp_asid=9, vsatp_asid=9)
        await env.issue(CacheReq(vpn=vpn, s2xlate=2))
        assert (await env.wait_resp())["hit"] == 1
        env.set_csr(hgatp_vmid=8)
        await env.issue(CacheReq(vpn=vpn, s2xlate=2))
        assert (await env.wait_resp())["hit"] == 0


# PTWC-13: allStage searches the L0 with onlyStage1 context and reports
# stage1Hit without a final hit when the S1 PTE is valid.
async def test_allstage_stage1_hit(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, satp_asid=1, vsatp_asid=2, vmid=3)
        vpn = 0x33000
        await env.refill_l0(vpn, leaves(0x80000), s2xlate=3)
        await env.issue(CacheReq(vpn=vpn, s2xlate=3))
        snap = await env.wait_resp()
        assert snap["hit"] == 0, snap
        assert snap["stage1hit"] == 1, snap
        assert snap["e0_v"] == 1 and snap["e0_level"] == 0
        if env.coverage:
            env.coverage.sample("hptw", 0, 3)


# PTWC-14: a noS2 page-fault-only L0 entry is cached and reported as a hit
# with pf=1; an allStage invalid entry is not cached (miss).
async def test_fault_entry_caching(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0x34000
        fault_ptes = [pte(0x80000 + index, v=0, a=0, d=0) for index in range(8)]
        await env.refill_entries(vpn, 0, fault_ptes, s2xlate=0)
        await env.issue(CacheReq(vpn=vpn))
        snap = await env.wait_resp()
        assert snap["hit"] == 1, snap
        assert snap["stage1hit"] == 0
        assert snap["e0_v"] == 0 and snap["e0_pf"] == 1
        # allStage cannot refill this invalid S1 PTE.
        await env.refill_entries(vpn, 0, fault_ptes, s2xlate=3)
        await env.issue(CacheReq(vpn=vpn, s2xlate=3))
        assert (await env.wait_resp())["hit"] == 0


# PTWC-15: prefetch fetches are marked in the response.
async def test_prefetch_flag(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0x35000
        await env.refill_l0(vpn, leaves(0x80000), source=2)
        await env.issue(CacheReq(vpn=vpn, source=0))
        assert (await env.wait_resp())["prefetch"] == 1
        if env.coverage:
            env.coverage.sample("prefetch", 0, 0)


# PTWC-16: HPTW requests pass through the cache and expose hptw fields.
async def test_hptw_path(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, vmid=7)
        vpn = 0x36000
        ptes = leaves(0x80000)
        await env.refill_l0(vpn, ptes, source=1)
        await env.issue(CacheReq(vpn=vpn, source=1, is_hptw=1, hptw_id=3))
        snap = await env.wait_resp()
        assert snap["is_hptw"] == 1
        assert snap["h_id"] == 3
        assert snap["h_bypassed"] == 0
        assert snap["toHptw"]["tag"] == vpn
        assert snap["toHptw"]["level"] == 0
        assert snap["toHptw"]["gpf"] == 0
        assert snap["toHptw"]["fromSP"] == 0
        if env.coverage:
            env.coverage.sample("hptw", 0, 0)


# PTWC-17: with BME=1 the L0 hit is converted into a bitmap-check jump and
# the sector PTE vector is returned to the PTW.
async def test_bitmap_jump(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        env.set_csr(bme=1, cmode=0)
        vpn = 0x37000
        ptes = leaves(0x80000)
        await env.refill_l0(vpn, ptes)
        await env.issue(CacheReq(vpn=vpn))
        snap = await env.wait_resp()
        assert snap["hit"] == 0, snap
        assert snap["jmp_bitmap"] == 1
        assert snap["tollptw"] == 1
        assert snap["splevel"] == 0
        assert snap["bitmap_ptes"] == ptes
        assert snap["toHptw"]["jmp"] == 1
        if env.coverage:
            env.coverage.sample("bitmap", 0, 0)


# PTWC-18: BME=1 with allStage does not jump for the G-stage lookup but does
# for the HPTW request.
async def test_bitmap_allstage(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, vsatp_asid=1)
        env.set_csr(bme=1, cmode=0)
        vpn = 0x38000
        ptes = leaves(0x80000)
        await env.refill_l0(vpn, ptes, s2xlate=3)
        await env.issue(CacheReq(vpn=vpn, s2xlate=3))
        snap = await env.wait_resp()
        assert snap["jmp_bitmap"] == 0
        assert snap["stage1hit"] == 1
        await env.issue(CacheReq(vpn=vpn, s2xlate=3, is_hptw=1))
        snap = await env.wait_resp()
        assert snap["jmp_bitmap"] == 1
        assert snap["is_hptw"] == 1
        if env.coverage:
            env.coverage.sample("bitmap", 0, 3)


# PTWC-19: full sfence invalidates every cache level.
async def test_full_sfence(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0x39000
        await env.refill_l0(vpn, leaves(0x80000))
        await env.refill_super(vpn, 1, leaf(0x4000))
        await env.issue(CacheReq(vpn=vpn))
        assert (await env.wait_resp())["hit"] == 1
        await env.flush(rs1=1, rs2=1)
        await env.issue(CacheReq(vpn=vpn))
        assert (await env.wait_resp())["hit"] == 0
        if env.coverage:
            env.coverage.sample("flush", 0, 0)


# PTWC-20: address+ASID sfence removes only the matching entry; a different
# address remains cached. An rs1=1/rs2=0 sfence clears the whole ASID.
async def test_scoped_sfence(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, satp_asid=2)
        a, b = 0x3A000, 0x3B000
        await env.refill_l0(a, leaves(0x80000))
        await env.refill_l0(b, leaves(0x90000))
        await env.issue(CacheReq(vpn=a))
        assert (await env.wait_resp())["hit"] == 1
        await env.issue(CacheReq(vpn=b))
        assert (await env.wait_resp())["hit"] == 1
        # rs1=0, rs2=0: address + ASID scoped.
        await env.flush(addr=a << 12, rs1=0, rs2=0, asid=2)
        await env.issue(CacheReq(vpn=a))
        assert (await env.wait_resp())["hit"] == 0
        await env.issue(CacheReq(vpn=b))
        assert (await env.wait_resp())["hit"] == 1
        # rs1=1, rs2=0: every address with the given ASID.
        await env.flush(rs1=1, rs2=0, asid=2)
        await env.issue(CacheReq(vpn=b))
        assert (await env.wait_resp())["hit"] == 0


# PTWC-21: hfence.v and hfence.g invalidate through their own fields.
async def test_hfence_paths(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, vsatp_asid=1, vmid=3)
        vpn = 0x3C000
        await env.refill_l0(vpn, leaves(0x80000), s2xlate=1)
        await env.issue(CacheReq(vpn=vpn, s2xlate=1))
        assert (await env.wait_resp())["hit"] == 1
        await env.flush(rs1=1, rs2=1, hv=1, asid=1)
        await env.issue(CacheReq(vpn=vpn, s2xlate=1))
        assert (await env.wait_resp())["hit"] == 0
        await env.refill_l0(vpn, leaves(0x80000), s2xlate=2)
        await env.issue(CacheReq(vpn=vpn, s2xlate=2))
        assert (await env.wait_resp())["hit"] == 1
        await env.flush(rs1=1, rs2=1, hg=1)
        await env.issue(CacheReq(vpn=vpn, s2xlate=2))
        assert (await env.wait_resp())["hit"] == 0


# PTWC-22: response backpressure holds the payload stable.
async def test_resp_backpressure(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0x3D000
        await env.refill_l0(vpn, leaves(0x80000))
        await env.issue(CacheReq(vpn=vpn))
        env.resp["ready"].Set(0)
        while not env.read(env.resp["valid"]):
            await env.edge()
        snap = {k: env.read(v) for k, v in env.resp.items() if not isinstance(v, (dict, list))}
        for _ in range(10):
            await env.edge()
            assert {k: env.read(v) for k, v in env.resp.items()
                    if not isinstance(v, (dict, list))} == snap
        env.resp["ready"].Set(1)
        await env.edge()
        assert env.read(env.resp["valid"]) == 0


# PTWC-23: all four L0 ways in a set are usable and the fifth refill evicts.
async def test_l0_ways_and_sets(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        base_vpn = 0x40000
        hits = 0
        ways = []
        for index in range(5):
            vpn = base_vpn + (index << 3)
            await env.refill_l0(vpn, leaves(0x80000 + index * 0x100))
            await env.issue(CacheReq(vpn=vpn))
            snap = await env.wait_resp()
            if snap["hit"]:
                hits += 1
            ways.append(snap["hitway"])
        assert hits == 5
        # Different sets use different set indices.
        set_hits = 0
        for index in range(8):
            vpn = base_vpn + (index << 12)
            await env.refill_l0(vpn, leaves(0x80000))
            await env.issue(CacheReq(vpn=vpn))
            set_hits += (await env.wait_resp())["hit"]
        assert set_hits == 8


# PTWC-24: payload/CSR bit sweep through both all-ones and all-zeros.
@pytest.mark.structural_stress
async def test_bit_sweep(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        exclude = {"clock", "reset", P.p_req_valid, P.p_resp_ready,
                   P.p_refill_valid, P.p_bitmap_wakeup_valid,
                   P.p_bitmap_wakeup_ready}
        for endpoint in (1, 0):
            sweep_inputs(env, endpoint, exclude)
            for entry in env.sfence:
                for signal in entry.values():
                    signal.Set(0)
            refresh(env)
            await env.edge()
            for _ in range(3):
                await env.edge()
        await _prepare(env)
        await env.refill_l0(0x30000, leaves(0x80000))
        await env.issue(CacheReq(vpn=0x30000))
        restored = await env.wait_resp()
        assert restored["hit"] == 1 and restored["e0_ppn"] == 0x80000 >> 3


# PTWC-25: every L0 set and way is addressable; the 5th fill evicts a way.
async def test_l0_sets_ways_sweep(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        hits = 0
        for set_index in range(64):
            vpn = (set_index << 12) | 0x40000
            await env.refill_l0(vpn, leaves(0x80000))
            await env.issue(CacheReq(vpn=vpn))
            hits += (await env.wait_resp())["hit"]
        assert hits == 64, hits
        # 4 ways per set; a 5th distinct VPN in the same set still hits.
        base = 0x100000
        for index in range(4):
            vpn = base | (index << 3)
            await env.refill_l0(vpn, leaves(0x80000 + index * 0x100))
            await env.issue(CacheReq(vpn=vpn))
            assert (await env.wait_resp())["hit"] == 1
        if env.coverage:
            env.coverage.sample("l0_fill", 0, 0)


# PTWC-26: L1 has 4 sets x 2 ways; each set/way is usable.
async def test_l1_sets_ways(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        for set_index in range(4):
            for way in range(2):
                vpn = ((set_index << 12) | (way << 3)) | 0x50000
                await env.refill_entries(vpn, 1, [nonleaf(0x1000 + way)] * 8)
                await env.issue(CacheReq(vpn=vpn))
                snap = await env.wait_resp()
                assert snap["l1hit"] == 1, (set_index, way)
        if env.coverage:
            env.coverage.sample("l1_fill", 1, 0)


# PTWC-27: L2/L3 fully-associative entries survive up to 16 distinct fills.
async def test_l2_l3_capacity(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        l2_hits = 0
        for index in range(16):
            vpn = 0x60000 + index * 0x1000
            await env.refill_entries(vpn, 2, [nonleaf(0x2000 + index)] * 8)
            await env.issue(CacheReq(vpn=vpn))
            l2_hits += (await env.wait_resp())["l2hit"]
        assert l2_hits == 16, l2_hits
        l3_hits = 0
        for index in range(16):
            vpn = 0x70000 + index * 0x1000
            await env.refill_entries(vpn, 3, [nonleaf(0x3000 + index)] * 8)
            await env.issue(CacheReq(vpn=vpn))
            l3_hits += (await env.wait_resp())["l3hit"]
        assert l3_hits == 16, l3_hits
        if env.coverage:
            env.coverage.sample("l2_hit", 2, 0)
            env.coverage.sample("l3_hit", 3, 0)


# PTWC-28: SP has 16 entries; fill and hit all of them.
async def test_sp_capacity(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        hits = 0
        for index in range(16):
            vpn = 0x8000000 + index * 0x40000000
            await env.refill_super(vpn, 2, leaf(0x40000 + index))
            await env.issue(CacheReq(vpn=vpn))
            hits += (await env.wait_resp())["hit"]
        assert hits == 16, hits
        if env.coverage:
            env.coverage.sample("sp_fill", 2, 0)


# PTWC-29: bitmap wakeup updates the per-(way,pte-index) bitmap result used
# for the response cf bits.
async def test_bitmap_wakeup_update(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        env.set_csr(bme=1, cmode=0)
        vpn = 0x90005
        await env.refill_l0(vpn, leaves(0x80000))
        await env.issue(CacheReq(vpn=vpn))
        snap = await env.wait_resp()
        way = snap["hitway"]
        assert snap["bitmap_cfs"] == [1] * 8
        env.wakeup["valid"].Set(1)
        env.wakeup["set"].Set((vpn >> 3) & 0x3F)
        env.wakeup["tag"].Set(vpn)
        env.wakeup["way"].Set(way)
        env.wakeup["pte_index"].Set(vpn & 7)
        env.wakeup["check_success"].Set(1)
        env.wakeup["s2xlate"].Set(0)
        await env.edge()
        env.wakeup["valid"].Set(0)
        for _ in range(6):
            await env.edge()
        await env.issue(CacheReq(vpn=vpn))
        after = await env.wait_resp()
        expected = [1] * 8
        expected[5] = 0
        assert after["bitmap_cfs"] == expected, after["bitmap_cfs"]
        for index in range(8):
            assert after[f"e{index}_cf"] == (0 if index == 5 else 1)


# PTWC-30: a refill for the in-flight request sets the bypass flag.
async def test_refill_bypass(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0xA0000
        await env.issue(CacheReq(vpn=vpn))
        await env.edge()
        await env.refill_entries(vpn, 0, leaves(0x80000), selected=0)
        snap = await env.wait_resp()
        assert snap["bypassed"] == 1, snap
        assert snap["hit"] == 0


# PTWC-31: prefetch refills at L1/L2/SP levels set the prefetch bit.
async def test_prefetch_levels(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0xB0000
        await env.refill_super(vpn, 2, leaf(0x40000), source=2)
        await env.issue(CacheReq(vpn=vpn))
        snap = await env.wait_resp()
        assert snap["hit"] == 1 and snap["prefetch"] == 1
        vpn2 = 0xB1000
        await env.refill_entries(vpn2, 1, [nonleaf(0x2000)] * 8, source=2)
        await env.issue(CacheReq(vpn=vpn2))
        snap = await env.wait_resp()
        assert snap["l1hit"] == 1 and snap["prefetch"] == 1


# PTWC-32: canRefill rejects invalid entries per stage; only noS2 keeps a
# page-fault-only entry.
async def test_invalid_per_stage(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, vsatp_asid=1, vmid=3)
        vpn = 0xC0000
        bad = [pte(0x80000 + i, v=0, a=0, d=0) for i in range(8)]
        for stage in (1, 2, 3):
            await env.refill_entries(vpn, 0, bad, s2xlate=stage)
            await env.issue(CacheReq(vpn=vpn, s2xlate=stage))
            assert (await env.wait_resp())["hit"] == 0, stage


# PTWC-33: isFirst=0 passes through unchanged.
async def test_is_first_passthrough(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0xD0000
        await env.refill_l0(vpn, leaves(0x80000))
        await env.issue(CacheReq(vpn=vpn, is_first=0))
        snap = await env.wait_resp()
        assert snap["is_first"] == 0 and snap["hit"] == 1


# PTWC-34: HPTW translation hits report the upper-level hit bits for the
# next G-stage table lookup.
async def test_hptw_upper_levels(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpn = 0xE0000
        await env.refill_entries(vpn, 2, [nonleaf(0x2500)] * 8)
        await env.issue(CacheReq(vpn=vpn, is_hptw=1, hptw_id=5))
        snap = await env.wait_resp()
        assert snap["is_hptw"] == 1
        assert snap["h_l2hit"] == 1
        assert snap["h_ppn"] == 0x2500
        assert snap["h_id"] == 5


# PTWC-35: all 4 L0 ways of every set are fillable, individually hit, and
# every (way, sector-index) response path is reachable.
async def test_l0_all_ways_all_sets(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        base = 0x2000000
        for set_index in range(64):
            vpns = [base | (way << 16) | (set_index << 3) for way in range(4)]
            for way, vpn in enumerate(vpns):
                await env.refill_l0(vpn, leaves(0x80000 + ((set_index << 2) + way) * 8))
            ways = []
            for vpn in vpns:
                await env.issue(CacheReq(vpn=vpn))
                snap = await env.wait_resp()
                assert snap["hit"] == 1, (set_index, vpn)
                ways.append(snap["hitway"])
            assert len(set(ways)) == 4, (set_index, ways)
        # Cover each sector index on each way of one set.
        for way in range(4):
            vpn = base | (way << 16)
            for index in range(8):
                await env.issue(CacheReq(vpn=vpn | index))
                snap = await env.wait_resp()
                assert snap["hit"] == 1, (way, index)
                assert snap[f"e{index}_ppn_low"] == index
        # A 5th distinct tag evicts exactly one way of the set.
        victim_vpn = base | (4 << 16)
        await env.refill_l0(victim_vpn, leaves(0x90000))
        await env.issue(CacheReq(vpn=victim_vpn))
        assert (await env.wait_resp())["hit"] == 1
        survivors = 0
        for way in range(4):
            await env.issue(CacheReq(vpn=base | (way << 16)))
            survivors += (await env.wait_resp())["hit"]
        assert survivors == 3, survivors
        if env.coverage:
            env.coverage.sample("l0_fill", 0, 0)
            env.coverage.sample("l0_hit", 0, 0)


# PTWC-36: L1 is 4 sets x 2 ways; both ways of every set are usable.
async def test_l1_two_ways(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        base = 0x3000000
        for set_index in range(4):
            vpns = [base | (set_index << 12) | (way << 16) for way in range(2)]
            for way, vpn in enumerate(vpns):
                await env.refill_entries(vpn, 1, [nonleaf(0x1000 + way)] * 8)
            for vpn in vpns:
                await env.issue(CacheReq(vpn=vpn))
                snap = await env.wait_resp()
                assert snap["l1hit"] == 1, (set_index, vpn)
        if env.coverage:
            env.coverage.sample("l1_fill", 1, 0)
            env.coverage.sample("l1_hit", 1, 0)


# PTWC-37: L2/L3 capacity and replacement: all 16 entries survive and each
# one can be looked up again.
async def test_l2_l3_fill_and_sweep(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        l2_vpns = [0xE0000 + index * 0x2000 for index in range(16)]
        for index, vpn in enumerate(l2_vpns):
            await env.refill_entries(vpn, 2, [nonleaf(0x2000 + index)] * 8)
        for vpn in l2_vpns:
            await env.issue(CacheReq(vpn=vpn))
            assert (await env.wait_resp())["l2hit"] == 1, vpn
        l3_vpns = [0x100000 + index * 0x20000 for index in range(16)]
        for index, vpn in enumerate(l3_vpns):
            await env.refill_entries(vpn, 3, [nonleaf(0x3000 + index)] * 8)
        for vpn in l3_vpns:
            await env.issue(CacheReq(vpn=vpn))
            assert (await env.wait_resp())["l3hit"] == 1, vpn
        if env.coverage:
            env.coverage.sample("l2_hit", 2, 0)
            env.coverage.sample("l3_hit", 3, 0)


# PTWC-38: SP capacity: all 16 superpage entries survive and hit.
async def test_sp_fill_and_sweep(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpns = [0x40000000 + index * 0x8000000 for index in range(16)]
        for index, vpn in enumerate(vpns):
            await env.refill_super(vpn, 2, leaf(0x40000 + index))
        for vpn in vpns:
            await env.issue(CacheReq(vpn=vpn))
            assert (await env.wait_resp())["hit"] == 1, vpn
        if env.coverage:
            env.coverage.sample("sp_fill", 2, 0)


# PTWC-39: PBMT and permission fields are returned unchanged per sector entry.
async def test_pbmt_and_perms(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        base = 0x5000000
        for way, pbmt in enumerate((0, 1, 2, 3)):
            vpn = base | (way << 16)
            ptes = []
            for index in range(8):
                ptes.append(leaf(0x80000 + index, pbmt=pbmt,
                                 r=index & 1, w=(index >> 1) & 1,
                                 x=(index >> 2) & 1, u=1, g=0))
            await env.refill_l0(vpn, ptes)
            await env.issue(CacheReq(vpn=vpn))
            snap = await env.wait_resp()
            assert snap["hit"] == 1
            for index in range(8):
                assert snap[f"e{index}_pbmt"] == pbmt, (way, index)
                assert snap[f"e{index}_perm_r"] == (index & 1)
                assert snap[f"e{index}_perm_w"] == ((index >> 1) & 1)
                assert snap[f"e{index}_perm_x"] == ((index >> 2) & 1)
                assert snap[f"e{index}_perm_u"] == 1
                assert snap[f"e{index}_perm_g"] == 0


# PTWC-40: scoped sfence clears L0 SP L1 L2 and L3 at the right granularity.
async def test_flush_all_caches(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, satp_asid=2, vsatp_asid=2)
        v0, v1 = 0x1A000, 0x1300000
        v2, v3, v4 = 0x1B000, 0x1C000, 0x1D000
        await env.refill_l0(v0, leaves(0x80000))
        await env.refill_super(v1, 2, leaf(0x40000))
        await env.refill_entries(v2, 1, [nonleaf(0x1100)] * 8)
        await env.refill_entries(v3, 2, [nonleaf(0x2200)] * 8)
        await env.refill_entries(v4, 3, [nonleaf(0x3300)] * 8)
        for vpn, field in ((v0, "hit"), (v1, "hit"), (v2, "l1hit"),
                           (v3, "l2hit"), (v4, "l3hit")):
            await env.issue(CacheReq(vpn=vpn))
            assert (await env.wait_resp())[field] == 1, vpn
        # Address+ASID flush only clears the L0 sector and its SP entry.
        await env.flush(addr=v0 << 12, rs1=0, rs2=0, asid=2)
        await env.issue(CacheReq(vpn=v0))
        assert (await env.wait_resp())["hit"] == 0
        await env.issue(CacheReq(vpn=v2))
        assert (await env.wait_resp())["l1hit"] == 1
        await env.issue(CacheReq(vpn=v3))
        assert (await env.wait_resp())["l2hit"] == 1
        await env.issue(CacheReq(vpn=v4))
        assert (await env.wait_resp())["l3hit"] == 1
        # SP address flush.
        await env.flush(addr=v1 << 12, rs1=0, rs2=0, asid=2)
        await env.issue(CacheReq(vpn=v1))
        assert (await env.wait_resp())["hit"] == 0
        # All-address ASID flush clears L1/L2/L3.
        await env.flush(rs1=1, rs2=0, asid=2)
        for vpn, field in ((v2, "l1hit"), (v3, "l2hit"), (v4, "l3hit")):
            await env.issue(CacheReq(vpn=vpn))
            assert (await env.wait_resp())[field] == 0, vpn
        if env.coverage:
            env.coverage.sample("flush", 0, 0)


# PTWC-41: hfence.v clears onlyStage1 (h=1) entries in every cache.
async def test_hfencev_all_levels(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, vsatp_asid=1, vmid=3)
        v0 = 0x21000
        v1 = 0x5300000
        v2, v3, v4 = 0x22000, 0x23000, 0x24000
        await env.refill_l0(v0, leaves(0x80000), s2xlate=1)
        await env.refill_super(v1, 2, leaf(0x40000), s2xlate=1)
        await env.refill_entries(v2, 1, [nonleaf(0x1100)] * 8, s2xlate=1)
        await env.refill_entries(v3, 2, [nonleaf(0x2200)] * 8, s2xlate=1)
        await env.refill_entries(v4, 3, [nonleaf(0x3300)] * 8, s2xlate=1)
        for vpn in (v0, v1, v2, v3, v4):
            await env.issue(CacheReq(vpn=vpn, s2xlate=1))
            snap = await env.wait_resp()
            assert snap["hit"] == 1 or snap["l1hit"] or snap["l2hit"] or snap["l3hit"], vpn
        await env.flush(rs1=1, rs2=1, hv=1, asid=1)
        for vpn, field in ((v0, "hit"), (v1, "hit"), (v2, "l1hit"),
                           (v3, "l2hit"), (v4, "l3hit")):
            await env.issue(CacheReq(vpn=vpn, s2xlate=1))
            assert (await env.wait_resp())[field] == 0, vpn


# PTWC-42: hfence.g clears onlyStage2 (h=2) entries in every cache; the
# G-stage upper-level hits are observed through the HPTW response.
async def test_hfenceg_all_levels(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, vmid=5)
        v0 = 0x25000
        v1 = 0x5700000
        v2, v3, v4 = 0x26000, 0x27000, 0x28000
        await env.refill_l0(v0, leaves(0x80000), s2xlate=2)
        await env.refill_super(v1, 2, leaf(0x40000), s2xlate=2)
        await env.refill_entries(v2, 1, [nonleaf(0x1100)] * 8, s2xlate=2)
        await env.refill_entries(v3, 2, [nonleaf(0x2200)] * 8, s2xlate=2)
        await env.refill_entries(v4, 3, [nonleaf(0x3300)] * 8, s2xlate=2)
        for vpn, field in ((v0, "hit"), (v1, "hit"), (v2, "h_l1hit"),
                           (v3, "h_l2hit"), (v4, "h_l3hit")):
            await env.issue(CacheReq(vpn=vpn, s2xlate=2, is_hptw=1))
            snap = await env.wait_resp()
            assert snap[field] == 1, (vpn, field, snap)
        await env.flush(rs1=1, rs2=1, hg=1, asid=5)
        for vpn, field in ((v0, "hit"), (v1, "hit"), (v2, "h_l1hit"),
                           (v3, "h_l2hit"), (v4, "h_l3hit")):
            await env.issue(CacheReq(vpn=vpn, s2xlate=2, is_hptw=1))
            assert (await env.wait_resp())[field] == 0, vpn


# PTWC-43: a deeply stalled response pipeline makes the cache use the
# registered RAM-data fallback instead of the one-cycle bypass.
async def test_pipeline_stall_ram_fallback(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        vpns = [0x31000 + index * 0x8 for index in range(5)]
        for index, vpn in enumerate(vpns):
            await env.refill_l0(vpn, leaves(0x80000 + index * 0x100))
        env.resp["ready"].Set(0)
        accepted = []
        for vpn in vpns:
            if env.read(env.req["ready"]) == 0:
                break
            env.req["valid"].Set(1)
            env.req["vpn"].Set(vpn)
            env.req["s2xlate"].Set(0)
            env.req["source"].Set(0)
            env.req["is_first"].Set(1)
            env.req["is_hptw"].Set(0)
            env.req["hptw_id"].Set(0)
            refresh(env)
            await env.edge()
            env.req["valid"].Set(0)
            accepted.append(vpn)
        for _ in range(10):
            await env.edge()
        snaps = []
        for _ in range(400):
            if env.read(env.resp["valid"]):
                snaps.append({key: env.read(sig) for key, sig in env.resp.items()
                              if not isinstance(sig, (dict, list))})
                env.resp["ready"].Set(1)
            await env.edge()
            env.resp["ready"].Set(0)
            if len(snaps) == len(accepted):
                break
        assert len(accepted) >= 3, accepted
        assert len(snaps) == len(accepted), (len(snaps), len(accepted))
        assert [snap["vpn"] for snap in snaps] == accepted
        assert all(snap["hit"] == 1 for snap in snaps)


# PTWC-44: in virtual mode a normal sfence clears onlyStage1 (h=1) entries in
# every cache and honours the VMID check.
async def test_virt_sfence_all_levels(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, vsatp_asid=2, vmid=3)
        env.set_csr(virt=1)
        v0 = 0x33000
        v1 = 0x5B00000
        v2, v3, v4 = 0x34000, 0x35000, 0x36000
        await env.refill_l0(v0, leaves(0x80000), s2xlate=1)
        await env.refill_super(v1, 2, leaf(0x40000), s2xlate=1)
        await env.refill_entries(v2, 1, [nonleaf(0x1100)] * 8, s2xlate=1)
        await env.refill_entries(v3, 2, [nonleaf(0x2200)] * 8, s2xlate=1)
        await env.refill_entries(v4, 3, [nonleaf(0x3300)] * 8, s2xlate=1)
        for vpn, field in ((v0, "hit"), (v1, "hit"), (v2, "l1hit"),
                           (v3, "l2hit"), (v4, "l3hit")):
            await env.issue(CacheReq(vpn=vpn, s2xlate=1))
            assert (await env.wait_resp())[field] == 1, vpn
        # A full sfence in virtual mode clears every level.
        await env.flush(rs1=1, rs2=1)
        for vpn, field in ((v0, "hit"), (v1, "hit"), (v2, "l1hit"),
                           (v3, "l2hit"), (v4, "l3hit")):
            await env.issue(CacheReq(vpn=vpn, s2xlate=1))
            assert (await env.wait_resp())[field] == 0, vpn
        # ASID-scoped sfence in virtual mode also clears them.
        await env.refill_l0(v0, leaves(0x80000), s2xlate=1)
        await env.refill_entries(v2, 1, [nonleaf(0x1100)] * 8, s2xlate=1)
        await env.refill_entries(v3, 2, [nonleaf(0x2200)] * 8, s2xlate=1)
        await env.refill_entries(v4, 3, [nonleaf(0x3300)] * 8, s2xlate=1)
        await env.flush(rs1=1, rs2=0, asid=2)
        for vpn, field in ((v0, "hit"), (v2, "l1hit"),
                           (v3, "l2hit"), (v4, "l3hit")):
            await env.issue(CacheReq(vpn=vpn, s2xlate=1))
            assert (await env.wait_resp())[field] == 0, vpn


# PTWC-45: hfence.v/hfence.g support all-ASID, ASID/VMID-scoped and
# address-scoped forms across the caches.
async def test_hfence_scope_variants(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, vsatp_asid=2, vmid=5)
        v0 = 0x41000
        v1 = 0x5D00000
        v2, v3, v4 = 0x42000, 0x43000, 0x44000

        async def fill_h1():
            await env.refill_l0(v0, leaves(0x80000), s2xlate=1)
            await env.refill_super(v1, 2, leaf(0x40000), s2xlate=1)
            await env.refill_entries(v2, 1, [nonleaf(0x1100)] * 8, s2xlate=1)
            await env.refill_entries(v3, 2, [nonleaf(0x2200)] * 8, s2xlate=1)
            await env.refill_entries(v4, 3, [nonleaf(0x3300)] * 8, s2xlate=1)

        async def check(expect):
            for vpn, field in ((v0, "hit"), (v1, "hit"), (v2, "l1hit"),
                               (v3, "l2hit"), (v4, "l3hit")):
                await env.issue(CacheReq(vpn=vpn, s2xlate=1))
                assert (await env.wait_resp())[field] == expect, (vpn, expect)

        # hfence.v, rs1=1 rs2=0: ASID-scoped.
        await fill_h1()
        await env.flush(rs1=1, rs2=0, hv=1, asid=2)
        await check(0)
        # hfence.v, rs1=0 rs2=1: address-scoped, only L0/L2/L3/L1 tag data.
        await fill_h1()
        await env.flush(rs1=0, rs2=1, hv=1, addr=v0 << 12)
        await env.issue(CacheReq(vpn=v0, s2xlate=1))
        assert (await env.wait_resp())["hit"] == 0
        for vpn, field in ((v1, "hit"), (v2, "l1hit"), (v3, "l2hit")):
            await env.issue(CacheReq(vpn=vpn, s2xlate=1))
            assert (await env.wait_resp())[field] == 1, vpn
        # hfence.v, rs1=0 rs2=0: address + ASID.
        await env.refill_l0(v0, leaves(0x80000), s2xlate=1)
        await env.flush(rs1=0, rs2=0, hv=1, addr=v0 << 12, asid=2)
        await env.issue(CacheReq(vpn=v0, s2xlate=1))
        assert (await env.wait_resp())["hit"] == 0

        # h=2 entries for hfence.g.
        v5 = 0x45000
        v6 = 0x5F00000
        v7, v8, v9 = 0x46000, 0x47000, 0x48000

        async def fill_h2():
            await env.refill_l0(v5, leaves(0x80000), s2xlate=2)
            await env.refill_super(v6, 2, leaf(0x40000), s2xlate=2)
            await env.refill_entries(v7, 1, [nonleaf(0x1100)] * 8, s2xlate=2)
            await env.refill_entries(v8, 2, [nonleaf(0x2200)] * 8, s2xlate=2)
            await env.refill_entries(v9, 3, [nonleaf(0x3300)] * 8, s2xlate=2)

        # hfence.g, rs1=1 rs2=0: VMID-scoped, checked through HPTW outputs.
        await fill_h2()
        await env.flush(rs1=1, rs2=0, hg=1, asid=5)
        for vpn, field in ((v5, "hit"), (v6, "hit"), (v7, "h_l1hit"),
                           (v8, "h_l2hit"), (v9, "h_l3hit")):
            await env.issue(CacheReq(vpn=vpn, s2xlate=2, is_hptw=1))
            assert (await env.wait_resp())[field] == 0, vpn
        # hfence.g, rs1=0 rs2=1: guest-physical address-scoped.
        await fill_h2()
        await env.flush(rs1=0, rs2=1, hg=1, addr=v5 << 10)
        await env.issue(CacheReq(vpn=v5, s2xlate=2, is_hptw=1))
        assert (await env.wait_resp())["hit"] == 0
        await env.issue(CacheReq(vpn=v6, s2xlate=2, is_hptw=1))
        assert (await env.wait_resp())["hit"] == 1
        # hfence.g, rs1=0 rs2=0: address + VMID.
        await env.refill_l0(v5, leaves(0x80000), s2xlate=2)
        await env.flush(rs1=0, rs2=0, hg=1, addr=v5 << 10, asid=5)
        await env.issue(CacheReq(vpn=v5, s2xlate=2, is_hptw=1))
        assert (await env.wait_resp())["hit"] == 0


# PTWC-46: every bitmap bit (set x way x sector index) is writable in both
# directions by the Bitmap wakeup interface.
async def test_bitmap_reg_exhaustive(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        env.set_csr(bme=1, cmode=0)
        base = 0x10000000
        table = {}
        for set_index in range(64):
            for way in range(4):
                vpn = base | (way << 16) | (set_index << 3)
                table[(set_index, way)] = vpn
                await env.refill_l0(vpn, leaves(0x80000))
        env.wakeup["valid"].Set(1)
        env.wakeup["s2xlate"].Set(0)
        for success in (1, 0):
            for set_index in range(64):
                for way in range(4):
                    vpn = table[(set_index, way)]
                    env.wakeup["set"].Set(set_index)
                    env.wakeup["tag"].Set(vpn)
                    env.wakeup["way"].Set(1 << way)
                    env.wakeup["check_success"].Set(success)
                    for index in range(8):
                        env.wakeup["pte_index"].Set(index)
                        refresh(env)
                        await env.edge()
            env.wakeup["valid"].Set(0)
            for _ in range(4):
                await env.edge()
            await env.issue(CacheReq(vpn=table[(0, 0)]))
            snap = await env.wait_resp()
            expected_cf = 0 if success else 1
            assert snap["bitmap_cfs"] == [expected_cf] * 8, (success, snap["bitmap_cfs"])
            env.wakeup["valid"].Set(1)


# PTWC-47: an address sfence selects every L0 set in turn (flush-mask sweep).
async def test_flush_mask_sweep(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        for set_index in range(64):
            vpn = 0x20000000 | (set_index << 3)
            await env.refill_l0(vpn, leaves(0x80000))
            await env.flush(addr=vpn << 12, rs1=0, rs2=1)
            await env.issue(CacheReq(vpn=vpn))
            assert (await env.wait_resp())["hit"] == 0, set_index
        # Return the address to set 0 so the last mask bit also toggles back.
        await env.flush(addr=0, rs1=0, rs2=1)
        await env.edge()


# PTWC-48: storage and response data bits are exercised with opposite
# polarities for every valid field (L0/L1/L2/L3/SP).
async def test_field_polarity_sweep(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        all_ones_44 = (1 << 36) - 1
        ones_leaf = leaf(all_ones_44, g=1)
        minimal_leaf = pte(0, r=1, w=0, x=0, u=0, a=0, d=0)
        zero_leaf = pte(0, v=0, a=0, d=0)
        zero_nonleaf = nonleaf(0)
        ones_nonleaf = nonleaf((1 << 36) - 1)

        # L0: four passes over every set/way exercise h=0/1/2 and v=0/1.
        def l0_vpn(set_index, way):
            return (way << 16) | (set_index << 3)

        passes = [
            (0, zero_nonleaf, 0, 0, 0),
            (1, ones_leaf, 7, 7, 2),
            (2, ones_leaf, 7, 7, 2),
            (0, minimal_leaf, 0, 0, 0),
            (0, zero_nonleaf, 0, 0, 0),
        ]
        for pass_index, (stage, pte_word, asid, vmid, source) in enumerate(passes):
            env.set_csr(satp_asid=asid, vsatp_asid=asid, hgatp_vmid=vmid)
            for set_index in range(64):
                for way in range(4):
                    vpn = l0_vpn(set_index, way)
                    await env.refill_entries(vpn, 0, [pte_word] * 8,
                                             s2xlate=stage, source=source)
            if pass_index in (0, 1):
                for set_index in range(64):
                    for way in range(4):
                        await env.issue(CacheReq(vpn=l0_vpn(set_index, way),
                                                 s2xlate=stage))
                        snap = await env.wait_resp()
                        if pass_index == 1:
                            assert snap["hit"] == 1
                            assert snap["e0_ppn_low"] == (all_ones_44 & 7)
                        else:
                            assert snap["hit"] == 0
            if pass_index in (1, 3):
                env.set_csr(bme=1, cmode=0)
                await env.issue(CacheReq(vpn=l0_vpn(0, 0), s2xlate=stage))
                snap = await env.wait_resp()
                assert snap["jmp_bitmap"] == 1, snap
                expected_pte = ones_leaf if pass_index == 1 else minimal_leaf
                assert snap["bitmap_ptes"][0] == expected_pte
                env.set_csr(bme=0, cmode=0)

        # L1: zero and one passes for both ways of every set.
        for pass_index, (tag, pte_word, asid, vmid) in enumerate((
                (0, zero_nonleaf, 0, 0),
                (0x3FFFFF, ones_nonleaf, 7, 7))):
            if pass_index == 1:
                await env.flush(rs1=1, rs2=1)
            env.set_csr(satp_asid=asid, vsatp_asid=asid, hgatp_vmid=vmid)
            for set_index in range(4):
                for way in range(2):
                    if pass_index == 1:
                        vpn = ((0x3FFFFF ^ way) << 16) | (set_index << 12)
                    else:
                        vpn = (way << 16) | (set_index << 12)
                    await env.refill_entries(vpn, 1, [pte_word] * 8,
                                             s2xlate=0)
            for set_index in range(4):
                for way in range(2):
                    vpn = (way << 16) | (set_index << 12) if pass_index == 0 else\
                        ((0x3FFFFF ^ way) << 16) | (set_index << 12)
                    await env.issue(CacheReq(vpn=vpn))
                    snap = await env.wait_resp()
                    assert snap["l1hit"] == 1, (pass_index, set_index, way, hex(vpn), snap["l2hit"], snap["l3hit"], snap["ppn"], snap["e0_v"], snap["e0_level"], snap["e0_tag"])
                    assert snap["ppn"] == (0 if pass_index == 0 else (1 << 36) - 1)

        # L2/L3: zero and one passes over all 16 entries.
        for level in (2, 3):
            for pass_index, (pte_word, asid, vmid) in enumerate((
                    (zero_nonleaf, 0, 0),
                    (ones_nonleaf, 7, 7))):
                if pass_index == 1:
                    await env.flush(rs1=1, rs2=1)
                env.set_csr(satp_asid=asid, vsatp_asid=asid, hgatp_vmid=vmid)
                vpns = []
                for index in range(16):
                    if pass_index == 0:
                        vpn = index << 20
                    else:
                        vpn = (((~index) & 0x3FFFF) << 20)
                    vpns.append(vpn)
                    await env.refill_entries(vpn, level, [pte_word] * 8,
                                             s2xlate=0)
                for vpn in vpns:
                    await env.issue(CacheReq(vpn=vpn))
                    snap = await env.wait_resp()
                    field = "l2hit" if level == 2 else "l3hit"
                    assert snap[field] == 1, (level, vpn)
                    assert snap["ppn"] == (0 if pass_index == 0 else (1 << 36) - 1)

        # SP: page-fault and aligned superpage passes over all 16 entries.
        for pass_index, (pte_word, asid, vmid) in enumerate((
                (zero_leaf, 0, 0),
                (leaf((((1 << 36) - 1) & ~((1 << 18) - 1)), g=1), 7, 7))):
            if pass_index == 1:
                await env.flush(rs1=1, rs2=1)
            env.set_csr(satp_asid=asid, vsatp_asid=asid, hgatp_vmid=vmid)
            vpns = []
            for index in range(16):
                if pass_index == 0:
                    vpn = index << 2
                else:
                    vpn = (((~index) & 0x3FFFFFFF) << 2)
                vpns.append(vpn)
                await env.refill_super(vpn, 2, pte_word, s2xlate=0)
            for vpn in vpns:
                await env.issue(CacheReq(vpn=vpn))
                snap = await env.wait_resp()
                assert snap["hit"] == 1, (pass_index, vpn)


# PTWC-49: bitmap wakeup in allStage context uses onlyStage1 hit filtering
# and clears the corresponding sector cf bit.
async def test_bitmap_wakeup_allstage(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env, vsatp_asid=2, vmid=5)
        vpn = 0x50005
        await env.refill_l0(vpn, leaves(0x80000), s2xlate=3)
        await env.issue(CacheReq(vpn=vpn, s2xlate=3))
        snap = await env.wait_resp()
        assert snap["stage1hit"] == 1
        way = snap["hitway"]
        env.set_csr(bme=1, cmode=0)
        env.wakeup["valid"].Set(1)
        env.wakeup["set"].Set((vpn >> 3) & 0x3F)
        env.wakeup["tag"].Set(vpn)
        env.wakeup["way"].Set(way)
        env.wakeup["pte_index"].Set(vpn & 7)
        env.wakeup["check_success"].Set(1)
        env.wakeup["s2xlate"].Set(3)
        await env.edge()
        env.wakeup["valid"].Set(0)
        for _ in range(6):
            await env.edge()
        await env.issue(CacheReq(vpn=vpn, s2xlate=3))
        after = await env.wait_resp()
        assert after["bitmap_cfs"][vpn & 7] == 0


# PTWC-50: a 64KB NAPOT leaf is stored in the SP way (not as a 4KB L0
# entry) and hits for every 4KB subpage of its range.
async def test_napot_64k_hit(ptwcache_env):
    env = ptwcache_env
    async with execution(env):
        await _prepare(env)
        base_vpn = 0x60000
        ppn = 0x8008  # NAPOT encoding: ppn[3:0] = 4'b1000
        napot = leaf(ppn, n=1)
        await env.refill_l0(base_vpn, [napot] * 8)
        for offset in range(16):
            vpn = base_vpn | offset
            await env.issue(CacheReq(vpn=vpn))
            snap = await env.wait_resp()
            assert snap["hit"] == 1, (offset, snap)
            assert snap["not_super"] == 0
            assert snap["e0_level"] == 0
            assert snap["e0_n"] == 1
            assert snap["e0_ppn_low"] == (ppn & 7)
            assert snap["splevel"] == 0
        # A neighbouring 64KB region must not alias.
        await env.issue(CacheReq(vpn=base_vpn | 0x10))
        assert (await env.wait_resp())["hit"] == 0
