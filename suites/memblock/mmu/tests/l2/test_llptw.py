"""LLPTW standalone tests."""
from __future__ import annotations

import pytest

from mmuverify.common.runtime import execution
from mmuverify.l2.llptw import LlpReq
from mmuverify.l2.l2tlb import pte


def _leaves(env, base_ppn: int, vpn_low: int, final_ppns=None, **perms) -> None:
    perms = perms or dict(r=1, w=1, x=1, u=1, a=1, d=1)
    for index in range(8):
        ppn = (final_ppns or [0x1000 + index] * 1)[0] if final_ppns else 0x1000 + index
        if final_ppns:
            ppn = final_ppns[index]
        env.memory.write((base_ppn << 12) + (vpn_low + index) * 8,
                         pte(ppn, **perms))


async def _prepare(env) -> None:
    await env.reset()


# LLPTW-01: a normal noS2 request reads the 64-byte PTE block, reports no
# access fault and issues the page-cache update request.
async def test_normal_walk(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        _leaves(env, 0x80002, 0)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, source=1))
        snap = await env.wait_out(note="normal")
        assert snap["vpn"] == 0x30000
        assert snap["source"] == 1 and snap["s2xlate"] == 0
        assert snap["af"] == 0 and snap["first_s2_fault"] == 0
        assert snap["h"]["gpf"] == 0 and snap["h"]["gaf"] == 0
        assert env.mem_requests and env.mem_requests[0]["addr"] == (0x80002 << 12)
        assert len(env.mem_requests) == 1
        if env.coverage:
            env.coverage.sample("walk", 0, "pass")


# LLPTW-02: a non-zero vpn_low read starts at the corresponding PTE offset.
async def test_vpn_low_offset(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        _leaves(env, 0x80002, 5)
        await env.issue(LlpReq(vpn=0x30005, ppn=0x80002))
        snap = await env.wait_out(note="vpn low")
        assert snap["af"] == 0
        assert env.mem_requests[0]["addr"] == (0x80002 << 12) + 5 * 8


# LLPTW-04: PMP denial reports af without issuing a memory request.
async def test_pmp_fault(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        _leaves(env, 0x80002, 0)
        for entry in env.pmp:
            entry["ld"].Set(1)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002))
        snap = await env.wait_out(note="pmp")
        assert snap["af"] == 1
        assert env.mem_requests == []
        if env.coverage:
            env.coverage.sample("fault", 0, "fail")


# LLPTW-05: after one walk completes, a second distinct request is accepted
# and produces its own output.
async def test_sequential_requests(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        _leaves(env, 0x80002, 0)
        _leaves(env, 0x80003, 0)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, source=1))
        first = await env.wait_out(note="seq 0")
        await env.issue(LlpReq(vpn=0x50000, ppn=0x80003, source=2))
        second = await env.wait_out(note="seq 1")
        assert first["vpn"] == 0x30000 and first["source"] == 1
        assert second["vpn"] == 0x50000 and second["source"] == 2


# LLPTW-06: duplicate VPN requests share the in-flight memory read.
async def test_duplicate_request(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        _leaves(env, 0x80002, 0)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, source=1))
        await env.service(2)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, source=2))
        a = await env.wait_out(note="dup a")
        assert a["vpn"] == 0x30000
        assert len(env.mem_requests) == 1, env.mem_requests
        if env.coverage:
            env.coverage.sample("dup", 0, "pass")


# LLPTW-07: the output is held stable while ready is low.
async def test_out_backpressure(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        _leaves(env, 0x80002, 0)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002))
        while not env.read(env.out["valid"]):
            await env.service(1)
        snap = {key: env.read(sig) for key, sig in env.out.items()}
        ptes = [env.read(sig) for sig in env.out_ptes]
        for _ in range(10):
            await env.edge()
            assert {key: env.read(sig) for key, sig in env.out.items()} == snap
            assert [env.read(sig) for sig in env.out_ptes] == ptes
        env.out["ready"].Set(1)
        await env.edge()
        assert env.read(env.out["valid"]) == 0


# LLPTW-08: sfence in the middle of the walk drops the request.
async def test_flush_mid_walk(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        _leaves(env, 0x80002, 0)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002))
        await env.service(1)
        env.sfence.Set(1)
        await env.service(3)
        env.sfence.Set(0)
        await env.service(3)
        assert env.read(env.out["valid"]) == 0
        assert env.read(env.inp["ready"]) == 1
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002))
        assert (await env.wait_out(note="after flush"))["vpn"] == 0x30000
        if env.coverage:
            env.coverage.sample("flush", 0, "pass")


# LLPTW-09: mem.req.mask blocks the entry until it is cleared.
async def test_mem_req_mask(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        _leaves(env, 0x80002, 0)
        env.masks[0].Set(1)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002))
        for _ in range(10):
            await env.service(1)
        assert env.mem_requests == []
        env.sfence.Set(1)
        await env.service(2)
        env.sfence.Set(0)
        env.masks[0].Set(0)
        await env.service(2)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002))
        snap = await env.wait_out(note="after mask")
        assert snap["af"] == 0


# LLPTW-10: a bitmap-jump request uses the supplied PTE vector and bitmap
# results, without a page-table memory read.
async def test_bitmap_jump(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        env.csr["bme"].Set(1)
        env.csr["cmode"].Set(0)
        env.dut.RefreshComb()
        env.bitmap_cf = 1
        env.bitmap_cfs_value = 0b00010000
        ptes = [pte(0x2000 + index, r=1, w=1, x=1, u=1, a=1, d=1) for index in range(8)]
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, ptes=ptes,
                               cfs=0b00010000, jmp_bitmap=1, hitway=4))
        snap = await env.wait_out(note="bitmap")
        assert snap["jmp_bitmap"] == 1
        assert snap["ptes"] == ptes
        assert snap["cfs"] == [0, 0, 0, 0, 1, 0, 0, 0]
        assert env.mem_requests == []
        assert env.bitmap_requests
        assert snap["af"] == 1, snap
        if env.coverage:
            env.coverage.sample("bitmap", 4, "fail")




# LLPTW-11: all six entry slots can hold active walks at once.
async def test_capacity(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        for index in range(6):
            _leaves(env, 0x80010 + index, 0)
            await env.issue(LlpReq(vpn=0x40000 + index * 0x2000,
                                   ppn=0x80010 + index, source=index))
            await env.service(3)
        assert env.read(env.inp["ready"]) == 0
        seen = []
        for _ in range(6):
            snap = await env.wait_out(note="capacity")
            seen.append(snap["vpn"])
        assert sorted(seen) == sorted(0x40000 + index * 0x2000 for index in range(6))
        assert env.read(env.inp["ready"]) == 1
        if env.coverage:
            env.coverage.sample("capacity", 0, "pass")


# LLPTW-15: every vpn_low offset (lane) and 64-byte block is exercised.
async def test_lane_offsets(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        for low in range(8):
            _leaves(env, 0x80020 + low, low)
            await env.issue(LlpReq(vpn=0x60000 + low, ppn=0x80020 + low))
            snap = await env.wait_out(note=f"lane {low}")
            assert snap["af"] == 0
            if env.coverage:
                env.coverage.sample("walk", low, "pass")


# LLPTW-STAGE2-01: an allStage request first translates the leaf-table guest
# address, reads the PTE block through that translation, then translates the
# final leaf PPN.  Both HPTW requests and the identity-mapped memory read are
# observable, and the output carries the final stage-2 entry.
async def test_stage2_identity_translation(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        env.hptw_enabled = True
        env.hptw["ready"].Set(1)
        env.dut.RefreshComb()
        _leaves(env, 0x80002, 0, final_ppns=[0x1000 + index for index in range(8)])
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, s2xlate=3, source=1))
        snap = await env.wait_out(note="stage2 identity")
        assert snap["h"]["ppn"] == 0x1000, snap["h"]
        assert snap["h"]["level"] == 0
        assert snap["h"]["gpf"] == 0 and snap["h"]["gaf"] == 0
        assert snap["h"]["perm_r"] == 1 and snap["h"]["perm_w"] == 1
        assert snap["h"]["perm_x"] == 1 and snap["h"]["perm_a"] == 1
        assert snap["first_s2_fault"] == 0 and snap["af"] == 0
        assert len(env.hptw_requests) == 2, env.hptw_requests
        assert env.hptw_requests[0]["gvpn"] == 0x80002, env.hptw_requests
        assert env.hptw_requests[1]["gvpn"] == 0x1000, env.hptw_requests
        assert env.mem_requests[0]["addr"] == (0x80002 << 12)
        assert len(env.mem_requests) == 1
        if env.coverage:
            env.coverage.sample("stage2", 0, "pass")


# LLPTW-STAGE2-02: a first-stage-2 GPF stops the walk before any PTE memory
# read and marks first_s2xlate_fault.
async def test_stage2_first_fault_gpf(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        env.hptw_enabled = True
        env.hptw["ready"].Set(1)
        env.hptw_gpf = 1
        env.dut.RefreshComb()
        _leaves(env, 0x80002, 0, final_ppns=[0x1000] * 8)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, s2xlate=3, source=1))
        snap = await env.wait_out(note="stage2 first gpf")
        assert snap["h"]["gpf"] == 1 and snap["h"]["gaf"] == 0, snap["h"]
        assert snap["first_s2_fault"] == 1
        assert snap["af"] == 0
        assert env.mem_requests == []
        if env.coverage:
            env.coverage.sample("stage2", 0, "fail")


# LLPTW-STAGE2-03: a first-stage-2 GAF has the same stop/no-read behavior as
# GPF but reports gaf.
async def test_stage2_first_fault_gaf(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        env.hptw_enabled = True
        env.hptw["ready"].Set(1)
        env.hptw_gaf = 1
        env.dut.RefreshComb()
        _leaves(env, 0x80002, 0, final_ppns=[0x1000] * 8)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, s2xlate=3, source=1))
        snap = await env.wait_out(note="stage2 first gaf")
        assert snap["h"]["gaf"] == 1 and snap["h"]["gpf"] == 0, snap["h"]
        assert snap["first_s2_fault"] == 1
        assert snap["af"] == 0
        assert env.mem_requests == []
        if env.coverage:
            env.coverage.sample("stage2", 0, "fail")


# LLPTW-STAGE2-04: the first stage-2 translation succeeds, the leaf is read,
# and only the final stage-2 translation faults.  The output reports gpf
# without setting first_s2xlate_fault.
async def test_stage2_last_fault_gpf(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        env.hptw_enabled = True
        env.hptw["ready"].Set(1)
        env.hptw_gpf_last = 1
        env.dut.RefreshComb()
        _leaves(env, 0x80002, 0, final_ppns=[0x1000] * 8)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, s2xlate=3, source=1))
        snap = await env.wait_out(note="stage2 last gpf")
        assert snap["h"]["gpf"] == 1 and snap["h"]["gaf"] == 0, snap["h"]
        assert snap["first_s2_fault"] == 0
        assert snap["af"] == 0
        assert len(env.mem_requests) == 1
        assert len(env.hptw_requests) == 2
        if env.coverage:
            env.coverage.sample("stage2", 0, "fail")


# LLPTW-STAGE2-05: final stage-2 access fault after a successful PTE read.
async def test_stage2_last_fault_gaf(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        env.hptw_enabled = True
        env.hptw["ready"].Set(1)
        env.hptw_gaf_last = 1
        env.dut.RefreshComb()
        _leaves(env, 0x80002, 0, final_ppns=[0x1000] * 8)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, s2xlate=3, source=1))
        snap = await env.wait_out(note="stage2 last gaf")
        assert snap["h"]["gaf"] == 1 and snap["h"]["gpf"] == 0, snap["h"]
        assert snap["first_s2_fault"] == 0
        assert snap["af"] == 0
        assert len(env.mem_requests) == 1
        if env.coverage:
            env.coverage.sample("stage2", 0, "fail")


# LLPTW-STAGE2-06: onlyStage2 requests read the PTE block directly and do not
# issue HPTW requests; the stage-2 fault fields stay clear.
async def test_only_stage2_walk(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        _leaves(env, 0x80002, 0, final_ppns=[0x1000] * 8)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, s2xlate=2, source=1))
        snap = await env.wait_out(note="only stage2")
        assert snap["s2xlate"] == 2
        assert snap["af"] == 0 and snap["first_s2_fault"] == 0
        assert snap["h"]["gpf"] == 0 and snap["h"]["gaf"] == 0
        assert env.hptw_requests == []
        assert len(env.mem_requests) == 1
        if env.coverage:
            env.coverage.sample("stage2", 0, "pass")


# LLPTW-CACHE-01: a duplicate request that arrives while the first result is
# held in mem_out is not re-walked; it issues a page-cache update carrying the
# original VPN/s2xlate/source, then retires without a second output.
async def test_cache_retry_on_duplicate(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        _leaves(env, 0x80002, 0, final_ppns=[0x1000] * 8)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, source=0))
        env.out["ready"].Set(0)
        for _ in range(200):
            await env.service(1)
            if env.read(env.out["valid"]):
                break
        assert env.read(env.out["valid"]) == 1
        assert len(env.mem_requests) == 1
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, source=1))
        for _ in range(50):
            await env.service(1)
            if env.cache_requests:
                break
        assert env.cache_requests, "duplicate did not issue a cache update"
        cache = env.cache_requests[0]
        assert cache["vpn"] == 0x30000 and cache["s2xlate"] == 0
        assert cache["source"] == 1, cache
        assert len(env.mem_requests) == 1, env.mem_requests
        env.out["ready"].Set(1)
        await env.service(1)
        assert env.read(env.out["valid"]) == 0
        if env.coverage:
            env.coverage.sample("cache", 0, "pass")


async def _hold_normal_walks(env, count: int):
    """Start `count` normal walks and leave their results in mem_out."""
    cases = []
    for index in range(count):
        vpn = 0x30000 + index * 0x2000
        base = 0x80002 + index
        ppn = 0x1000 + index * 0x10
        _leaves(env, base, 0, final_ppns=[ppn] * 8)
        await env.issue(LlpReq(vpn=vpn, ppn=base, source=0))
        await env.service(6)
        cases.append((vpn, base, ppn))
    assert len(env.mem_requests) == count, env.mem_requests
    return cases


async def _drain_outputs(env, count: int):
    seen = []
    for _ in range(count):
        snap = await env.wait_out(note="slot drain", max_cycles=400)
        seen.append((snap["id"], snap["vpn"], snap["s2xlate"], snap["h"]["ppn"],
                     snap["jmp_bitmap"]))
    return seen


# LLPTW-SLOTS-01: every entry slot 1..5 can host an allStage request while the
# preceding slots hold completed normal results.  This exercises the per-entry
# first/last HPTW response fields, not just entry 0.
async def test_stage2_in_every_entry_slot(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        for count in range(1, 6):
            await _prepare(env)
            env.hptw_enabled = True
            env.hptw["ready"].Set(1)
            env.dut.RefreshComb()
            env.out["ready"].Set(0)
            held = await _hold_normal_walks(env, count)
            base = 0x80010
            leaf = 0x2000 + count * 0x10
            _leaves(env, base, 0, final_ppns=[leaf] * 8)
            before_mem = len(env.mem_requests)
            await env.issue(LlpReq(vpn=0x50000 + count * 0x2000,
                                   ppn=base, s2xlate=3, source=1))
            for _ in range(400):
                await env.service(1)
                if len(env.hptw_requests) >= 2 and len(env.mem_requests) >= before_mem + 1:
                    break
            seen = await _drain_outputs(env, count + 1)
            assert [item[0] for item in seen] == list(range(count + 1)), seen
            assert seen[-1][1] == 0x50000 + count * 0x2000
            assert seen[-1][2] == 3 and seen[-1][3] == leaf, seen[-1]
            assert len(env.hptw_requests) == 2, env.hptw_requests
            if env.coverage:
                env.coverage.sample("stage2", 0, "pass")


# LLPTW-SLOTS-02: every entry slot 1..5 can host a bitmap-jump request while
# preceding slots hold normal results.  The bitmap request id and output id
# both select the new slot; ptes/cfs are returned unchanged.
async def test_bitmap_in_every_entry_slot(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        for count in range(1, 6):
            await _prepare(env)
            env.out["ready"].Set(0)
            held = await _hold_normal_walks(env, count)
            env.csr["bme"].Set(1)
            env.csr["cmode"].Set(0)
            env.bitmap_cf = 1
            env.bitmap_cfs_value = (1 << 8) - 1
            env.dut.RefreshComb()
            ptes = [pte(0x3000 + index, r=1, w=1, x=1, u=1, a=1, d=1)
                    for index in range(8)]
            vpn = 0x60000 + count * 0x2000
            await env.issue(LlpReq(vpn=vpn, ppn=0x80002, ptes=ptes,
                                   cfs=(1 << 8) - 1, jmp_bitmap=1, hitway=3))
            for _ in range(300):
                await env.service(1)
                if env.bitmap_requests:
                    break
            assert env.bitmap_requests, "no bitmap request"
            request = env.bitmap_requests[-1]
            assert request["id"] == count, request
            assert request["vpn"] == vpn and request["way_info"] == 3, request
            seen = await _drain_outputs(env, count + 1)
            assert [item[0] for item in seen] == list(range(count + 1)), seen
            assert seen[-1][1] == vpn and seen[-1][4] == 1, seen[-1]
            if env.coverage:
                env.coverage.sample("bitmap", 0, "fail")


# LLPTW-SLOTS-03: a duplicate in every free slot 1..5 issues the page-cache
# update and retires without a second output or memory read.
async def test_cache_retry_in_every_entry_slot(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        for count in range(1, 6):
            await _prepare(env)
            env.out["ready"].Set(0)
            held = await _hold_normal_walks(env, count)
            before_mem = len(env.mem_requests)
            await env.issue(LlpReq(vpn=held[0][0], ppn=held[0][1], source=1))
            for _ in range(100):
                await env.service(1)
                if env.cache_requests:
                    break
            assert env.cache_requests, (count, "no cache update")
            cache = env.cache_requests[0]
            assert cache["vpn"] == held[0][0] and cache["source"] == 1, cache
            seen = await _drain_outputs(env, count)
            assert [item[0] for item in seen] == list(range(count)), seen
            for _ in range(20):
                await env.service(1)
                assert env.read(env.out["valid"]) == 0
            assert len(env.mem_requests) == before_mem, env.mem_requests
            if env.coverage:
                env.coverage.sample("cache", 0, "pass")


# LLPTW-STAGE2-07: a first-stage-2 HPTW response without R (and without the
# MXR/X escape) cannot be used as a page table; it is reported as a first
# stage-2 fault with no PTE memory read.
async def test_stage2_first_perm_fault(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        env.hptw_enabled = True
        env.hptw["ready"].Set(1)
        env.hptw_perm["r"] = 0
        env.hptw_perm["x"] = 0
        env.dut.RefreshComb()
        _leaves(env, 0x80002, 0, final_ppns=[0x1000] * 8)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, s2xlate=3, source=1))
        snap = await env.wait_out(note="stage2 perm fault")
        assert snap["h"]["gpf"] == 1, snap["h"]
        assert snap["first_s2_fault"] == 1
        assert snap["af"] == 0
        assert env.mem_requests == []
        if env.coverage:
            env.coverage.sample("stage2", 0, "fail")


# LLPTW-STAGE2-08: with MXR=1 and X permission, an R=0 stage-2 response is
# usable as a page table (execute-only table); the walk completes normally.
async def test_stage2_first_perm_mxr_pass(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        env.csr["mxr"].Set(1)
        env.hptw_enabled = True
        env.hptw["ready"].Set(1)
        env.hptw_perm["r"] = 0
        env.hptw_perm["x"] = 1
        env.dut.RefreshComb()
        _leaves(env, 0x80002, 0, final_ppns=[0x1000] * 8)
        await env.issue(LlpReq(vpn=0x30000, ppn=0x80002, s2xlate=3, source=1))
        snap = await env.wait_out(note="stage2 mxr pass")
        assert snap["h"]["gpf"] == 0 and snap["h"]["gaf"] == 0, snap["h"]
        assert snap["first_s2_fault"] == 0 and snap["af"] == 0
        assert len(env.mem_requests) == 1
        if env.coverage:
            env.coverage.sample("stage2", 0, "pass")


# Historical attribution superseded by verification-soundness-20261025.md.
# should each perform their two HPTW translations and PTE read.  The DUT
# issues three HPTW requests and one PTE read, then stalls; this is recorded as
# the LLPTW multi-allStage behavior gap (single allStage in every slot works).
@pytest.mark.parametrize("hptw_latency", [0, 1, 3])
async def test_two_concurrent_all_stage(llptw_env, hptw_latency):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        env.hptw_enabled = True
        env.hptw_resp_latency = hptw_latency
        env.hptw["ready"].Set(1)
        env.dut.RefreshComb()
        env.out["ready"].Set(0)
        for index in range(2):
            vpn = 0x30000 + index * 0x2000
            base = 0x80002 + index
            _leaves(env, base, 0, final_ppns=[0x1000 + index * 0x10] * 8)
            await env.issue(LlpReq(vpn=vpn, ppn=base, s2xlate=3, source=index))
            await env.service(4)
        outs = []
        for _ in range(2):
            snap = await env.wait_out(note="two allStage", max_cycles=500)
            index = (snap["vpn"] - 0x30000) // 0x2000
            assert index in (0, 1), snap
            assert snap["source"] == index and snap["s2xlate"] == 3, snap
            assert snap["af"] == 0 and snap["first_s2_fault"] == 0, snap
            assert snap["h"]["gpf"] == 0 and snap["h"]["gaf"] == 0, snap
            assert snap["h"]["ppn"] == 0x1000 + index * 0x10, snap
            outs.append(snap["vpn"])
        assert sorted(outs) == [0x30000, 0x32000]


async def test_consecutive_normal_requests_no_pmp_alias(llptw_env):
    env = llptw_env
    async with execution(env.dut):
        await _prepare(env)
        for index in range(2):
            _leaves(env, 0x80020 + index, 0, final_ppns=[0x2000 + index] * 8)
            await env.issue(LlpReq(vpn=0x40000 + index * 0x2000,
                                   ppn=0x80020 + index, source=index))
        snaps = [await env.wait_out(note="consecutive normal") for _ in range(2)]
        assert sorted(s["vpn"] for s in snaps) == [0x40000, 0x42000]
        assert all(s["af"] == 0 and s["first_s2_fault"] == 0 for s in snaps), snaps
        assert sorted(s["source"] for s in snaps) == [0, 1]
        assert len(env.mem_requests) == 2, env.mem_requests
