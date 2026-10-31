"""BitmapCache standalone tests."""
from __future__ import annotations

from suites.memblock.mmu.execution import execution


DATA = 0x0102030405060708


async def test_refill_then_hit_selects_byte(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        await env.refill_word(0x80000, DATA)
        for index in range(8):
            await env.send(0x80000 + (index << 3), order=index)
            resp = await env.wait_resp()
            expected = (DATA >> (8 * index)) & 0xFF
            assert resp["hit"] == 1, index
            assert resp["order"] == index
            assert resp["cfs"] == [(expected >> bit) & 1 for bit in range(8)], (index, resp)
            if env.coverage:
                env.coverage.sample("hit", index, index)


async def test_miss_before_refill(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        await env.send(0x80000, order=1)
        resp = await env.wait_resp()
        assert resp["hit"] == 0
        assert resp["order"] == 1
        env.coverage.sample("miss", 0, 1) if env.coverage else None


async def test_two_tags_same_set(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        await env.refill_word(0x80000, 0xAAAAAAAAAAAAAAAA)
        await env.refill_word(0x81000, 0x5555555555555555)
        await env.send(0x80000)
        first = await env.wait_resp()
        await env.send(0x81000)
        second = await env.wait_resp()
        assert first["hit"] == 1 and first["cfs"] == [0, 1, 0, 1, 0, 1, 0, 1]
        assert second["hit"] == 1 and second["cfs"] == [1, 0, 1, 0, 1, 0, 1, 0]


async def test_four_ways_and_eviction(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        tags = [0x80000 + index * (1 << 11) for index in range(5)]
        for index, tag in enumerate(tags):
            await env.refill_word(tag, index + 1)
        # The fifth refill must evict one of the first four.
        hits = 0
        for tag in tags:
            await env.send(tag)
            resp = await env.wait_resp()
            hits += resp["hit"]
        assert hits == 4, hits


async def test_bclear_invalidates(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        await env.refill_word(0x80000, DATA)
        await env.send(0x80000)
        assert (await env.wait_resp())["hit"] == 1
        env.csr["bclear"].Set(1)
        await env.edge()
        env.csr["bclear"].Set(0)
        await env.edge()
        await env.send(0x80000)
        assert (await env.wait_resp())["hit"] == 0
        env.coverage.sample("clear", 0) if env.coverage else None


async def test_sfence_keeps_cache_and_bclear_invalidates(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        await env.refill_word(0x80000, DATA)
        for key in ("satp_changed", "vsatp_changed", "hgatp_changed", "virt_changed"):
            await env.send(0x80000)
            assert (await env.wait_resp())["hit"] == 1, key
            env.csr[key].Set(1)
            await env.edge()
            env.csr[key].Set(0)
            await env.edge()
            await env.send(0x80000)
            # Flush cancels in-flight work but does not invalidate bitmap data.
            assert (await env.wait_resp())["hit"] == 1, key
        env.sfence.Set(1)
        await env.edge()
        env.sfence.Set(0)
        await env.edge()
        await env.send(0x80000)
        assert (await env.wait_resp())["hit"] == 1
        env.csr["bclear"].Set(1)
        await env.edge()
        env.csr["bclear"].Set(0)
        await env.edge()
        await env.send(0x80000)
        assert (await env.wait_resp())["hit"] == 0
        env.coverage.sample("flush", 0) if env.coverage else None
        env.coverage.sample("clear", 0) if env.coverage else None


async def test_response_backpressure(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        await env.refill_word(0x80000, DATA)
        await env.send(0x80000, order=5)
        env.resp["ready"].Set(0)
        while not env.read(env.resp["valid"]):
            await env.edge()
        snap = {key: env.read(sig) for key, sig in env.resp.items()}
        cfs = [env.read(sig) for sig in env.cfs]
        for _ in range(10):
            await env.edge()
            assert {key: env.read(sig) for key, sig in env.resp.items()} == snap
            assert [env.read(sig) for sig in env.cfs] == cfs
        env.resp["ready"].Set(1)
        await env.edge()
        assert env.read(env.resp["valid"]) == 0


async def test_all_orders(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        await env.refill_word(0x80000, DATA)
        results = []
        for order in range(8):
            await env.send(0x80000, order=order)
            results.append(await env.wait_resp())
        assert [r["order"] for r in results] == list(range(8))
        assert all(r["hit"] == 1 for r in results)
        if env.coverage:
            for order in range(8):
                env.coverage.sample("hit", order, order)


async def test_data_extremes(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        for endpoint in (1, 0):
            tag = 0x80000 + endpoint * 0x800
            data = ((1 << 64) - 1) if endpoint else 0
            await env.refill_word(tag, data)
            await env.send(tag)
            resp = await env.wait_resp()
            assert resp["hit"] == 1
            assert resp["cfs"] == [endpoint] * 8


async def test_all_sets_and_bytes(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        # Fill one entry in every set (ppn[10:6]) and hit it via each byte lane
        # (ppn[5:3]); the lower 3 bits are ignored by the cache tag.
        for set_index in range(32):
            ppn = (set_index << 6) | (0x100 << 11)
            await env.refill_word(ppn, DATA)
        for set_index in range(32):
            for byte_index in range(8):
                ppn = (set_index << 6) | (0x100 << 11) | (byte_index << 3)
                await env.send(ppn, order=byte_index)
                resp = await env.wait_resp()
                expected = (DATA >> (8 * byte_index)) & 0xFF
                assert resp["hit"] == 1, (set_index, byte_index)
                assert resp["order"] == byte_index
                assert resp["cfs"] == [(expected >> bit) & 1 for bit in range(8)], (set_index, byte_index, resp)
                if env.coverage:
                    env.coverage.sample("hit", byte_index, byte_index)


async def test_tag_extremes(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        for tag, data in ((0, 0), ((1 << 36) - 1, (1 << 64) - 1),
                          (0x555555555, 0xAAAAAAAAAAAAAAAA)):
            await env.refill_word(tag, data)
            await env.send(tag)
            resp = await env.wait_resp()
            assert resp["hit"] == 1


async def test_all_ways_and_data_patterns(bitmapcache_env):
    env = bitmapcache_env
    async with execution(env):
        await env.reset()
        patterns = [0xFFFFFFFFFFFFFFFF, 0xAAAAAAAAAAAAAAAA,
                    0x5555555555555555, 0]
        entries = []
        for set_index in range(32):
            for way in range(4):
                ppn = (set_index << 6) | ((way + 1) << 11)
                await env.refill_word(ppn, patterns[way])
                entries.append((ppn, patterns[way]))
        for ppn, pattern in entries:
            await env.send(ppn)
            resp = await env.wait_resp()
            assert resp["hit"] == 1, hex(ppn)
        # A fifth refill in set 0 evicts exactly one way.
        await env.refill_word(0x10000 | (5 << 11), 0x0123456789ABCDEF)
        hits = 0
        for ppn, _pattern in entries[:4]:
            await env.send(ppn)
            hits += (await env.wait_resp())["hit"]
        assert hits == 3, hits


