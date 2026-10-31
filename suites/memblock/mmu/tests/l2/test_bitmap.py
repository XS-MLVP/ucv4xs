"""Bitmap standalone tests."""
from __future__ import annotations

from suites.memblock.mmu.execution import execution
import pytest

from suites.memblock.mmu.l2.bitmap import BmReq

BMA = 0x90000000 >> 6
BASE = 0x90000000


def word_for(ppn: int, set_bits: int) -> int:
    """Put `set_bits` (6 bits) as the bit/byte pattern of the selected word."""
    return set_bits


async def _prepare(env) -> None:
    await env.reset()
    env.csr["bma"].Set(BMA)
    env.wakeup["ready"].Set(1)
    await env.edge()


# BMP-01: cache hit returns cf and the full cfs byte.
async def test_cache_hit_pass_and_fail(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = True
        env.cache_cfs = 0x00
        await env.issue(BmReq(bmppn=0x80000, id=1))
        resp = await env.wait_resp(note="hit pass")
        assert resp["cf"] == 0 and resp["cfs"] == [0] * 8 and resp["id"] == 1
        env.cache_cfs = 0x01
        await env.issue(BmReq(bmppn=0x80000, id=2))
        resp = await env.wait_resp(note="hit fail")
        assert resp["cf"] == 1 and resp["cfs"][0] == 1 and resp["id"] == 2
        env.coverage.sample("cache_hit", 0, "fail") if env.coverage else None


# BMP-02: cf selects bit ppn[2:0] of the cached byte.
async def test_cache_hit_selects_bit(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = True
        for bit in range(8):
            env.cache_cfs = 1 << bit
            await env.issue(BmReq(bmppn=0x80000 | bit, id=bit))
            resp = await env.wait_resp(note=f"bit {bit}")
            assert resp["cf"] == 1 and resp["cfs"] == [(1 << bit >> j) & 1 for j in range(8)]
            if env.coverage:
                env.coverage.sample("cache_hit", 0, "fail")


# BMP-03: cache miss reads the 64-bit bitmap word and refills the cache with it.
async def test_cache_miss_reads_and_refills(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = False
        ppn = 0x80000 | 0b001001
        env.mem_value = 1 << 9
        await env.issue(BmReq(bmppn=ppn, vpn=0x12345, id=3))
        resp = await env.wait_resp(note="miss")
        assert resp["cf"] == 1 and resp["cfs"] == [0, 1, 0, 0, 0, 0, 0, 0]
        assert env.mem_requests and env.mem_requests[0]["addr"] == BASE + (ppn >> 6) * 8
        assert env.mem_requests[0]["id"] == 8
        assert env.refills and env.refills[0]["tag"] == ppn
        assert env.refills[0]["data"] == (1 << 9)
        env.coverage.sample("cache_miss", 0, "fail") if env.coverage else None
        env.coverage.sample("refill", 0, "fail") if env.coverage else None


# BMP-04: PMP denial fails the check without cache/memory traffic.
async def test_pmp_denied(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.pmp_deny = True
        await env.issue(BmReq(bmppn=0x80000, id=4))
        resp = await env.wait_resp(note="pmp fail")
        assert resp["cf"] == 1 and resp["cfs"] == [1] * 8 and resp["id"] == 4
        assert env.cache_requests == [] and env.mem_requests == []
        env.coverage.sample("pmp_fail", 0, "fail") if env.coverage else None


# BMP-05: page level merges VPN bits into the effective bitmap PPN.
async def test_level_merge(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = True
        env.cache_cfs = 0
        cases = [
            (1, 0x12345, (0x80000 & ~0x1FF) | (0x12345 & 0x1FF)),
            (2, 0x12345, (0x80000 & ~0x3FFFF) | (0x12345 & 0x3FFFF)),
            (3, 0x1234567, (0x80000 & ~0x7FFFFFF) | (0x1234567 & 0x7FFFFFF)),
        ]
        for level, vpn, expected in cases:
            env.cache_requests.clear()
            await env.issue(BmReq(bmppn=0x80000, vpn=vpn, level=level, id=level))
            assert (await env.wait_resp(note=f"level {level}"))["id"] == level
            assert env.cache_requests[0]["tag"] == expected, (level, env.cache_requests)
            if env.coverage:
                env.coverage.sample("cache_hit", level, "pass")


# BMP-06: NAPOT level-0 merges VPN[3:0] into the effective PPN.
async def test_napot_merge(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = True
        env.cache_cfs = 0
        await env.issue(BmReq(bmppn=0x80000, vpn=0xF, level=0, n=1, id=6))
        assert (await env.wait_resp(note="napot"))["id"] == 6
        expected = (0x80000 & ~0xF) | 0xF
        assert env.cache_requests[0]["tag"] == expected


# BMP-07: multiple outstanding requests return their own ids and results.
async def test_multiple_outstanding(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = True
        env.cache_cfs = 0xFF
        reqs = []
        for index in range(7):
            req = BmReq(bmppn=0x80000 | index, id=index)
            reqs.append(req)
            await env.issue(req)
            await env.service(3)
        seen = {}
        for _ in range(7):
            resp = await env.wait_resp(note="multi")
            seen[resp["id"]] = resp["cf"]
        assert seen == {index: 1 for index in range(7)}, seen
        env.coverage.sample("multi", 0, "fail") if env.coverage else None


# BMP-08: two requests for the same bitmap PPN both complete with correct
# results. Deduplication is best-effort and not asserted here.
async def test_duplicate_requests(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = True
        env.cache_cfs = 0x01
        await env.issue(BmReq(bmppn=0x80000, id=0))
        await env.service(3)
        await env.issue(BmReq(bmppn=0x80000, id=1))
        await env.service(3)
        r0 = await env.wait_resp(note="dup 0")
        r1 = await env.wait_resp(note="dup 1")
        assert {r0["id"], r1["id"]} == {0, 1}
        assert r0["cf"] == 1 and r1["cf"] == 1


# BMP-09: flush clears pending work and the block accepts new requests.
async def test_flush(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = False
        for index in range(3):
            await env.issue(BmReq(bmppn=0x80000 + index * 0x40, id=index))
        env.sfence.Set(1)
        await env.edge()
        env.sfence.Set(0)
        for _ in range(3):
            await env.edge()
        assert env.read(env.req["ready"]) == 1
        env.cache_hit = True
        env.cache_cfs = 0
        await env.issue(BmReq(bmppn=0x80000, id=7))
        assert (await env.wait_resp(note="after flush"))["id"] == 7
        env.coverage.sample("flush", 0, "pass") if env.coverage else None


# BMP-10: a level-0 non-NAPOT passing check raises wakeup for the L0 fill.
async def test_wakeup(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = True
        env.cache_cfs = 0
        await env.issue(BmReq(bmppn=0x80000, vpn=0x12345, level=0, way_info=5,
                              s2xlate=2, id=2))
        resp = await env.wait_resp(note="wakeup")
        assert resp["id"] == 2 and resp["cf"] == 0
        assert env.wakeup_events, "expected a wakeup"
        event = env.wakeup_events[-1]
        assert event["ok"] == 1
        assert event["way"] == 5 and event["s2xlate"] == 2
        assert event["pteidx"] == 0x5
        env.coverage.sample("wakeup", 0, "pass") if env.coverage else None
        # A failed bitmap check reports check_success=0.
        env.wakeup_events.clear()
        env.cache_cfs = 1
        await env.issue(BmReq(bmppn=0x80000, vpn=0x12345, level=0, id=3))
        failed = await env.wait_resp(note="wakeup fail")
        assert failed["id"] == 3 and failed["cf"] == 1, failed
        assert env.wakeup_events and env.wakeup_events[-1]["ok"] == 0
        # hptw_bypassed suppresses wakeup.
        env.wakeup_events.clear()
        await env.issue(BmReq(bmppn=0x80000, vpn=0x12345, level=0,
                              hptw_bypassed=1, id=4))
        bypassed = await env.wait_resp(note="no wakeup")
        assert bypassed["id"] == 4 and bypassed["cf"] == 1, bypassed
        assert env.wakeup_events == []


# BMP-11: wakeup backpressure blocks the response until wakeup is consumed.
async def test_wakeup_backpressure(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.wakeup["ready"].Set(0)
        env.cache_hit = True
        env.cache_cfs = 0
        await env.issue(BmReq(bmppn=0x80000, vpn=0x12345, level=0, id=1))
        for _ in range(10):
            await env.service(1)
        assert env.read(env.wakeup["valid"]) == 1
        assert env.read(env.resp["valid"]) == 0
        snap = {key: env.read(sig) for key, sig in env.wakeup.items()}
        for _ in range(5):
            await env.edge()
            assert {key: env.read(sig) for key, sig in env.wakeup.items()} == snap
        env.wakeup["ready"].Set(1)
        await env.edge()
        resp = await env.wait_resp(note="wakeup released")
        assert resp["id"] == 1 and resp["cf"] == 0


# BMP-12: all-ones and all-zero bitmap words drive both cf polarities.
async def test_memory_extremes(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = False
        for endpoint in (1, 0):
            env.mem_value = ((1 << 512) - 1) if endpoint else 0
            await env.issue(BmReq(bmppn=0x80000, id=endpoint))
            resp = await env.wait_resp(note=f"extreme {endpoint}")
            assert resp["cf"] == endpoint
            assert resp["cfs"] == [endpoint] * 8


# BMP-13 (xfail): two back-to-back requests must each get a PMP check and a
# cache lookup. The generated Bitmap uses a single-entry PMP-check pipeline
# Historical attribution superseded by verification-soundness-20261025.md.
# entry's check and leaves its own entry in addr_check, so only one cache
# Historical attribution superseded by verification-soundness-20261025.md.
# Historical attribution superseded by verification-soundness-20261025.md.
async def test_back_to_back_requests(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = True
        env.cache_cfs = 0
        await env.issue(BmReq(bmppn=0x80000, id=0))
        await env.issue(BmReq(bmppn=0x80001, id=1))
        for _ in range(30):
            await env.service(1)
        assert len(env.cache_requests) == 2, env.cache_requests
        responses = [await env.wait_resp(note="back-to-back response") for _ in range(2)]
        assert sorted(r["id"] for r in responses) == [0, 1], responses
        assert all(r["cf"] == 0 and r["cfs"] == [0] * 8 for r in responses), responses


# BMP-14: all eight bitmap word indices are read on cache misses and the
# entry array can be filled to capacity.
async def test_all_words_and_capacity(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = False
        env.mem_value = 0
        for index in range(8):
            ppn = 0x80000 | ((index + 1) << 6)
            await env.issue(BmReq(bmppn=ppn, vpn=index, level=0, id=index))
            resp = await env.wait_resp(note=f"word {index}")
            assert resp["id"] == index and resp["cf"] == 0
            assert env.mem_requests[-1]["addr"] == BASE + (((ppn >> 6) << 3))
        assert len(env.mem_requests) == 8
        # Fill all entry slots by stalling cache responses.
        env.auto_cache = False
        for index in range(8):
            await env.issue(BmReq(bmppn=0x81000 | index, id=index))
            await env.service(2)
        assert env.read(env.req["ready"]) == 0, "Bitmap entry array should be full"
        env.sfence.Set(1)
        await env.edge()
        env.sfence.Set(0)
        await env.service(2)
        assert env.read(env.req["ready"]) == 1
        env.auto_cache = True


# BMP-15: multiple wakeups cover every pteidx and s2xlate value.
async def test_wakeup_variants(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = True
        env.cache_cfs = 0
        for index in range(8):
            await env.issue(BmReq(bmppn=0x80000 | index, vpn=index, level=0,
                                  way_info=index, s2xlate=index % 4, id=index))
            assert (await env.wait_resp(note="wakeup variants"))["id"] == index
            event = env.wakeup_events[-1]
            assert event["pteidx"] == index
            assert event["s2xlate"] == index % 4
            assert event["way"] == index
            if env.coverage:
                env.coverage.sample("wakeup", 0, "pass")


# BMP-16: NAPOT bit/byte merge across all low-4 VPN values.
async def test_napot_variants(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = True
        env.cache_cfs = 0
        for low in range(16):
            env.cache_requests.clear()
            await env.issue(BmReq(bmppn=0x80000, vpn=low, level=0, n=1,
                                  id=low % 8))
            snap = await env.wait_resp(note=f"napot {low}")
            assert snap["id"] == low % 8 and snap["cf"] == 0, snap
            assert snap["cfs"] == [0] * 8, snap
            assert env.cache_requests[0]["tag"] == ((0x80000 & ~0xF) | low)


# BMP-17: level 1/2/3 merge with several VPN values, all levels sampled.
async def test_level_variants(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = True
        env.cache_cfs = 0x01
        masks = {1: 0x1FF, 2: 0x3FFFF, 3: 0x7FFFFFF}
        for level, mask in masks.items():
            for vpn in (0, 1, mask, 0x12345 & mask):
                env.cache_requests.clear()
                await env.issue(BmReq(bmppn=0x80000, vpn=vpn, level=level,
                                      id=level))
                assert (await env.wait_resp(note=f"level {level}"))["id"] == level
                expected = (0x80000 & ~mask) | (vpn & mask)
                assert env.cache_requests[0]["tag"] == expected, (level, vpn)
                if env.coverage:
                    env.coverage.sample("cache_hit", level, "pass")


# Historical attribution superseded by verification-soundness-20261025.md.
# Historical attribution superseded by verification-soundness-20261025.md.
# back-to-back PMP alias recorded as BITMAP-PMP-BACKTOBACK-LOST.
async def test_multi_miss(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = False
        env.mem_value = (1 << 64) - 1
        await env.issue(BmReq(bmppn=0x80000, id=0))
        await env.service(1)
        await env.issue(BmReq(bmppn=0x80008, id=1))
        seen = {}
        for _ in range(12):
            resp = await env.wait_resp(note="multi miss")
            seen[resp["id"]] = resp["cf"]
            if len(seen) == 2:
                break
        assert seen == {0: 1, 1: 1}, seen
        # These PPNs lie in the same bitmap fetch block and must coalesce.
        assert len(env.mem_requests) == 1, env.mem_requests
        assert len(env.refills) >= 1, env.refills
        if env.coverage:
            env.coverage.sample("cache_miss", 0, "fail")


async def test_distinct_bitmap_misses_are_not_coalesced(bitmap_env):
    env = bitmap_env
    async with execution(env):
        await _prepare(env)
        env.cache_hit = False
        env.mem_value = 0
        await env.issue(BmReq(bmppn=0x80000, id=0))
        await env.issue(BmReq(bmppn=0x80400, id=1))
        snaps = [await env.wait_resp(note="distinct bitmap miss") for _ in range(2)]
        assert sorted(s["id"] for s in snaps) == [0, 1]
        assert all(s["cf"] == 0 and s["cfs"] == [0] * 8 for s in snaps), snaps
        assert len(env.mem_requests) == 2, env.mem_requests
        assert len({r["addr"] for r in env.mem_requests}) == 2, env.mem_requests
