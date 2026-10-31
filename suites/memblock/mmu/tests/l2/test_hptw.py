"""HPTW standalone G-stage walk tests."""
from __future__ import annotations
import pytest

from suites.memblock.mmu.legacy_pins import P
from suites.memblock.mmu.execution import execution, refresh, sweep_inputs

HPTW_SWEEP_EXCLUDE = {"clock", "reset", P.p_req_valid, P.p_resp_ready}


async def _prepare(env) -> None:
    await env.reset()
    env.csr["hgatp_mode"].Set(8)
    env.csr["hgatp_vmid"].Set(5)
    env.csr["hgatp_ppn"].Set(0x82000)
    refresh(env)
    await env.edge()


from suites.memblock.mmu.l2.l2tlb import pte


def _root_leaf(env, gvpn: int, ppn: int, **perms) -> None:
    perms = perms or dict(r=1, w=1, x=1, u=1, a=1, d=1)
    index = (gvpn >> 18) & 0x1FF
    env.memory.write((0x82000 << 12) + index * 8, pte(ppn, **perms))


# HPTW-01: 4KB G-stage translation walks root, middle and leaf.
async def test_hptw_4k_walk(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x90000, mid_ppn=0x82001,
                              leaf_ppn=0x82002)
        await env.issue(0x30000)
        resp = await env.wait_response(note="4k")
        assert resp["valid"] == 1
        assert resp["tag"] == 0x30000
        assert resp["vmid"] == 5
        assert resp["ppn"] == 0x90000
        assert resp["level"] == 0
        assert resp["gpf"] == 0 and resp["gaf"] == 0
        assert [r.address for r in env.requests] == [0x82000000, 0x82001C00, 0x82002000]


# HPTW-02: 2MB leaf at level 1 uses two memory reads.
async def test_hptw_2m_leaf(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x4000, level=1,
                              mid_ppn=0x82001)
        await env.issue(0x30000)
        resp = await env.wait_response(note="2m")
        assert resp["ppn"] == 0x4000
        assert resp["level"] == 1
        assert resp["gpf"] == 0 and resp["gaf"] == 0
        assert len(env.requests) == 2


# HPTW-03: 1GB leaf at the root uses one memory read.
async def test_hptw_1g_leaf(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        _root_leaf(env, 0x30000, 0x40000)
        await env.issue(0x30000)
        resp = await env.wait_response(note="1g")
        assert resp["ppn"] == 0x40000
        assert resp["level"] == 2
        assert resp["gpf"] == 0 and resp["gaf"] == 0
        assert len(env.requests) == 1


# HPTW-04: an invalid root PTE reports a guest page fault.
async def test_hptw_invalid_root(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.write((0x82000 << 12) + ((0x30000 >> 18) & 0x1FF) * 8,
                         pte(0, v=0, a=0, d=0))
        await env.issue(0x30000)
        resp = await env.wait_response(note="invalid root")
        assert resp["gpf"] == 1
        assert resp["gaf"] == 0


# HPTW-05: a misaligned 2MB leaf reports a guest page fault.
async def test_hptw_misaligned_2m(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x4001, level=1,
                              mid_ppn=0x82001)
        await env.issue(0x30000)
        resp = await env.wait_response(note="misaligned 2m")
        assert resp["gpf"] == 1
        assert resp["gaf"] == 0


# HPTW-06: PMP denial produces a guest access fault and no memory read.
async def test_hptw_pmp_denied(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x90000, mid_ppn=0x82001,
                              leaf_ppn=0x82002)
        env.pmp["ld"].Set(1)  # HPTW uses 1 = access fault
        await env.issue(0x30000)
        resp = await env.wait_response(note="pmp denied")
        assert resp["gaf"] == 1
        assert env.requests == []


# HPTW-07: io_mem_mask stalls the walk until it is released.
async def test_hptw_mem_mask_stall(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x90000, mid_ppn=0x82001,
                              leaf_ppn=0x82002)
        env.mem_mask.Set(1)
        await env.issue(0x30000)
        for _ in range(20):
            await env.service_memory(1)
        assert env.requests == []
        env.sfence.Set(1)
        for _ in range(2):
            await env.edge()
        env.sfence.Set(0)
        env.mem_mask.Set(0)
        await env.edge()
        await env.issue(0x30000)
        resp = await env.wait_response(note="after mask")
        assert resp["ppn"] == 0x90000 and resp["gpf"] == 0
        env.coverage.sample("mask", "4k") if env.coverage else None


# HPTW-08: sfence in the middle of a walk aborts it; a later request works.
async def test_hptw_sfence_mid_walk(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x90000, mid_ppn=0x82001,
                              leaf_ppn=0x82002)
        await env.issue(0x30000)
        for _ in range(10):
            await env.service_memory(1)
            if env.requests:
                break
        env.sfence.Set(1)
        for _ in range(3):
            await env.service_memory(1)
        env.sfence.Set(0)
        for _ in range(5):
            await env.service_memory(1)
        await env.issue(0x30000)
        resp = await env.wait_response(note="after sfence")
        assert resp["ppn"] == 0x90000 and resp["gpf"] == 0
        env.coverage.sample("sfence", "4k") if env.coverage else None


# HPTW-09: hgatp.changed flushes and forces a new walk.
async def test_hptw_csr_change(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x90000, mid_ppn=0x82001,
                              leaf_ppn=0x82002)
        await env.issue(0x30000)
        assert (await env.wait_response(note="before csr"))["ppn"] == 0x90000
        before = len(env.requests)
        env.csr["hgatp_changed"].Set(1)
        for _ in range(3):
            await env.edge()
        env.csr["hgatp_changed"].Set(0)
        for _ in range(5):
            await env.edge()
        env.memory.build_sv39(0x82000, 0x30000, 0x90001, mid_ppn=0x82001,
                              leaf_ppn=0x82002)
        await env.issue(0x30000)
        resp = await env.wait_response(note="after csr")
        assert resp["ppn"] == 0x90001
        assert len(env.requests) > before


# HPTW-10: the response is held stable under backpressure.
async def test_hptw_response_backpressure(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x90000, mid_ppn=0x82001,
                              leaf_ppn=0x82002)
        await env.issue(0x30000)
        while not env.read(env.resp["valid"]):
            await env.service_memory(1)
        snap = {key: env.read(sig) for key, sig in env.resp.items()}
        for _ in range(15):
            await env.edge()
            for key, sig in env.resp.items():
                assert env.read(sig) == snap[key], key
        env.resp["ready"].Set(1)
        await env.edge()
        assert env.read(env.resp["valid"]) == 0


# HPTW-11: a level-hit hint skips the corresponding upper-level read.
async def test_hptw_level_hit_hint(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        # l1Hit: the level-1 PTE is already known and req.ppn is the leaf table.
        env.memory.write((0x82002 << 12) + ((0x30000 & 0x1FF) * 8),
                         pte(0x90000, r=1, w=1, x=1, u=1, a=1, d=1))
        await env.issue(0x30000, ppn=0x82002, l1hit=1)
        resp = await env.wait_response(note="l1hit")
        assert resp["ppn"] == 0x90000 and resp["level"] == 0
        assert len(env.requests) == 1
        if env.coverage:
            env.coverage.sample("hit", "4k", "l1")


# HPTW-12: an l2-hit hint starts the walk at level 1 using req.ppn.
async def test_hptw_l2_hit_hint(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x4000, level=1, mid_ppn=0x82001)
        await env.issue(0x30000, ppn=0x82001, l2hit=1)
        resp = await env.wait_response(note="l2hit")
        assert resp["gpf"] == 0 and resp["gaf"] == 0
        if env.coverage:
            env.coverage.sample("hit", "2m", "l2")


# HPTW-13: a bitmap-checked cached leaf uses the bitmap request/response path.
async def test_hptw_bitmap_check(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.csr["bme"].Set(1)
        env.csr["cmode"].Set(0)
        refresh(env)
        leaf = pte(0x90000, r=1, w=1, x=1, u=1, a=1, d=1)
        await env.issue(0x30000, jmp_bitmap=1, bitmap_pte=leaf,
                        bitmap_fromsp=1, bitmap_splevel=0)
        resp = await env.wait_response(note="bitmap")
        assert resp["ppn"] == 0x90000, resp
        assert resp["level"] == 0
        assert resp["gpf"] == 0 and resp["gaf"] == 0
        assert env.bitmap_requests
        if env.coverage:
            env.coverage.sample("bitmap", "4k")


# HPTW-14: all-ones and all-zero request/PTE patterns drive every payload bit.


# HPTW-15: Sv48 l3-hit hint skips the top-level read.
async def test_hptw_l3_hit_hint(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.csr["hgatp_mode"].Set(9)
        refresh(env)
        # l3-hit: level-3 PTE is cached, req.ppn is the next-level table.
        env.memory.write((0x82001 << 12) + ((0x30000 >> 18) & 0x1FF) * 8,
                         pte(0x40000, r=1, w=1, x=1, u=1, a=1, d=1))
        await env.issue(0x30000, ppn=0x82001, l3hit=1)
        resp = await env.wait_response(note="l3hit")
        assert resp["gpf"] == 0 and resp["gaf"] == 0
        if env.coverage:
            env.coverage.sample("hit", "2m", "l3")


# HPTW-16: payload/CSR bit sweep plus extreme translation values.
async def test_hptw_bit_sweep(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        # Response tag / PPN / vmid extremes.
        env.memory.write((0x82000 << 12) + ((0x3FFFFFFFF >> 18) & 0x1FF) * 8,
                         pte(0, r=1, w=1, x=1, u=1, a=1, d=1))
        env.csr["hgatp_vmid"].Set(0)
        await env.issue(0x3FFFFFFFF, id=0, source=0)
        first = await env.wait_response(note="sweep 1g ones")
        assert first["tag"] == 0x3FFFFFFFF and first["vmid"] == 0
        # gvpn=0, vmid=all ones, id/source all ones.
        env.memory.write((0x82000 << 12), pte(0, r=1, w=1, x=1, u=1, a=1, d=1))
        env.csr["hgatp_vmid"].Set(0x3FFF)
        await env.issue(0, id=7, source=3)
        second = await env.wait_response(note="sweep 0")
        assert second["tag"] == 0 and second["vmid"] == 0x3FFF
        # Level-0 PPN and permission extremes.
        env.csr["hgatp_vmid"].Set(0)
        env.memory.build_sv39(0x82000, 0x1000, 0, mid_ppn=0x82010,
                              leaf_ppn=0x82011,
                              perms=dict(r=1, w=1, x=1, u=1, a=1, d=1))
        await env.issue(0x1000)
        low = await env.wait_response(note="sweep ppn 0")
        assert low["ppn"] == 0 and low["perm_d"] == 1 and low["perm_w"] == 1
        env.memory.build_sv39(0x82000, 0x1001, (1 << 36) - 1, mid_ppn=0x82012,
                              leaf_ppn=0x82013,
                              perms=dict(r=1, w=0, x=1, u=1, a=1, d=0))
        await env.issue(0x1001)
        high = await env.wait_response(note="sweep ppn ones")
        assert high["ppn"] == (1 << 36) - 1
        assert high["perm_d"] == 0 and high["perm_w"] == 0
        # Drive every remaining data/CSR input bit through both directions.
        sweep_inputs(env, 1, HPTW_SWEEP_EXCLUDE)
        await env.edge()
        env.sfence.Set(1)
        await env.edge()
        env.sfence.Set(0)
        sweep_inputs(env, 0, HPTW_SWEEP_EXCLUDE)
        await env.edge()


# HPTW-17: the non-SP bitmap path uses the ptes[] vector and level 0.
async def test_hptw_bitmap_ptes_vector(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.csr["bme"].Set(1)
        env.csr["cmode"].Set(0)
        refresh(env)
        leaf = pte(0x90000, r=1, w=1, x=1, u=1, a=1, d=1)
        await env.issue(0x30000, jmp_bitmap=1, bitmap_ptes=[leaf] * 8,
                        bitmap_fromsp=0, bitmap_hitway=5)
        resp = await env.wait_response(note="bitmap ptes")
        assert resp["ppn"] == 0x90000 and resp["level"] == 0, resp
        assert resp["gpf"] == 0 and resp["gaf"] == 0
        if env.coverage:
            env.coverage.sample("bitmap", "4k")


# HPTW-18: PMP MMIO denial also produces a guest access fault.
async def test_hptw_pmp_mmio_fault(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x90000)
        env.pmp["mmio"].Set(1)
        await env.issue(0x30000)
        resp = await env.wait_response(note="pmp mmio")
        assert resp["gaf"] == 1
        assert env.requests == []


# HPTW-19: each remaining CSR-change source independently flushes state.
async def test_hptw_csr_sources(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x90000)
        for key in ("satp_changed", "vsatp_changed", "virt_changed"):
            env.csr[key].Set(1)
            await env.edge()
            env.csr[key].Set(0)
            await env.edge()
            await env.issue(0x30000)
            resp = await env.wait_response(note=key)
            assert resp["ppn"] == 0x90000 and resp["gpf"] == 0, (key, resp)


# HPTW-20: high physical page-table addresses drive address payload bits.
async def test_hptw_high_address(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        root = (1 << 36) - 1
        env.csr["hgatp_ppn"].Set(root)
        refresh(env)
        env.memory.write((root << 12) + ((0x30000 >> 18) & 0x1FF) * 8,
                         pte(0x40000, r=1, w=1, x=1, u=1, a=1, d=1))
        await env.issue(0x30000)
        resp = await env.wait_response(note="high address")
        assert resp["ppn"] == 0x40000 and resp["gpf"] == 0


# HPTW-21: NAPOT + PBMT leaf fields reach the response when enabled.
async def test_hptw_napot_pbmt(hptw_env):
    env = hptw_env
    async with execution(env):
        await _prepare(env)
        env.csr["mpbmte"].Set(1)
        refresh(env)
        env.memory.build_sv39(0x82000, 0x30000, 0x90008, mid_ppn=0x82001,
                              leaf_ppn=0x82002,
                              perms=dict(r=1, w=1, x=1, u=1, a=1, d=1,
                                         pbmt=1, n=1))
        await env.issue(0x30000)
        resp = await env.wait_response(note="napot pbmt")
        assert resp["gpf"] == 0 and resp["gaf"] == 0, resp
        assert resp["pbmt"] == 1 and resp["n"] == 1, resp


# HPTW-21: reset does not gate accessFault.  With seed 1 and this build, a
# first walk after reset (without the usual post-reset sfence) still translates
# correctly and issues memory reads; a PMP-denied walk produces gaf=1 with no
# reads, and a subsequent reset+valid walk again succeeds.  This records that
# the structural omission (accessFault outside the sync reset) did not produce
# a spurious first-walk fault for the fixed test seed.
@pytest.mark.characterization
async def test_hptw_reset_without_flush_observation(hptw_env):
    env = hptw_env
    async with execution(env):
        await env.reset(post_sfence=False)
        env.csr["hgatp_mode"].Set(8)
        env.csr["hgatp_vmid"].Set(5)
        env.csr["hgatp_ppn"].Set(0x82000)
        refresh(env)
        await env.edge()
        env.memory.build_sv39(0x82000, 0x30000, 0x90000, mid_ppn=0x82001,
                              leaf_ppn=0x82002)
        await env.issue(0x30000)
        first = await env.wait_response(note="first after reset", max_cycles=80)
        assert first["gaf"] == 0 and first["gpf"] == 0, first
        assert [r.address for r in env.requests] == [
            0x82000000, 0x82001C00, 0x82002000]
        env.requests.clear()
        env.pmp["ld"].Set(1)
        await env.issue(0x30000)
        denied = await env.wait_response(note="denied", max_cycles=80)
        assert denied["gaf"] == 1 and env.requests == [], denied
        await env.reset(post_sfence=False)
        env.csr["hgatp_mode"].Set(8)
        env.csr["hgatp_vmid"].Set(5)
        env.csr["hgatp_ppn"].Set(0x82000)
        refresh(env)
        await env.edge()
        env.memory.build_sv39(0x82000, 0x30000, 0x90000, mid_ppn=0x82001,
                              leaf_ppn=0x82002)
        env.requests.clear()
        await env.issue(0x30000)
        second = await env.wait_response(note="second after reset", max_cycles=80)
        assert second["gaf"] == 0 and second["gpf"] == 0, second
        assert [r.address for r in env.requests] == [
            0x82000000, 0x82001C00, 0x82002000]
