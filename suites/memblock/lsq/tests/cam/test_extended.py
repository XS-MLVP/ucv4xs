"""Cases added only after the first native line/semantic gap inventory."""
import random

import pytest

from suites.memblock.lsq.cam.types import Query, Write


async def test_complete_pool_through_each_write_lane(cam):
    env = cam
    for lane in range(3):
        values = [(0x1257 * (i + 1) ^ (lane * 0x5A5A)) & ((1 << env.spec["width"]) - 1)
                  for i in range(env.spec["size"])]
        await env.initialize_pool(values, lane=lane)


async def test_same_bank_and_cross_bank_parallel_updates(cam):
    env = cam
    await env.initialize_pool()
    per_bank = env.spec["size"] // env.spec["banks"]
    for bank in range(env.spec["banks"]):
        addresses = [bank * per_bank + i for i in range(3)]
        values = [0x8000 + bank * 0x20 + i for i in range(3)]
        old = [env.model.entries[a] for a in addresses]
        await env.cycle({i: Write(a, v, True) for i, (a, v) in enumerate(zip(addresses, values, strict=True))},
                        env.queries(values))
        await env.idle(env.spec["write_delay"], env.queries(values))
        await env.probe_values((*old, *values))
    for bank in range(env.spec["banks"]):
        addresses = (bank * per_bank, ((bank + 3) % 8) * per_bank + per_bank - 1,
                     ((bank + 6) % 8) * per_bank + 1)
        values = [0x9000 + bank * 0x40 + i for i in range(3)]
        old = [env.model.entries[a] for a in addresses]
        await env.cycle({i: Write(a, v, True) for i, (a, v) in enumerate(zip(addresses, values, strict=True))},
                        env.queries(values))
        await env.idle(env.spec["write_delay"], env.queries(values))
        await env.probe_values((*old, *values))
    await env.probe_values()


async def test_candidate_sets_scope_and_independent_queries(cam):
    env = cam
    if env.spec["kind"] == "byte_mask":
        values = await env.initialize_pool()
        for queries in ((0, 1), (3, 6), (0xFFFF, 0x8000), (0x5555, 0xAAAA)):
            result = await env.cycle(queries=env.queries(queries))
            for q, actual in zip(result.queries, result.masks, strict=True):
                assert actual == sum(1 << i for i, v in enumerate(values) if v & q.value)
        await env.probe_values()
        return

    size = env.spec["size"]
    per_bank = size // env.spec["banks"]
    values = [0x4000 + 4 * i for i in range(size)]
    values[0] = values[per_bank] = 0x1234
    values[1:4] = [0x1235, 0x1236, 0x1237]
    await env.initialize_pool(values)
    for value in (0x1234, 0xDEAD, 0x4000 + 4 * (size - 1),
                  0x1234 ^ 1, 0x1234 ^ (1 << (env.spec["width"] - 1))):
        result = await env.cycle(queries=env.queries((value, 0xDEAD)))
        for q, actual in zip(result.queries, result.masks, strict=True):
            assert actual == sum(1 << i for i, v in enumerate(values) if v == q.value)
    exact = await env.cycle(queries=env.queries((0x1234, 0xDEAD)))
    assert exact.masks[0] == (1 << 0) | (1 << per_bank)
    assert exact.masks[1] == 0
    # Exercise every retained address bit, not just a few popular values.
    for bit in range(env.spec["width"]):
        await env.cycle(queries=env.queries((0x1234 ^ (1 << bit), 0x1234)))
    if env.spec["kind"] == "address_line":
        result = await env.cycle(queries=(Query(0x1234, False), Query(0x1234, True)))
        assert result.masks[0] == (1 << 0) | (1 << per_bank)
        assert result.masks[1] == sum(1 << i for i in (0, 1, 2, 3, per_bank))
        result = await env.cycle(queries=(Query(0x1237, True), Query(0x1237, False)))
        assert result.masks[0] == sum(1 << i for i in (0, 1, 2, 3, per_bank))
        assert result.masks[1] == 1 << 3
        await env.cycle(queries=(Query(0x1238, True), Query(0x1234, True)))


async def test_back_to_back_reuse_and_interleaved_bank_writes(cam):
    env = cam
    values = await env.initialize_pool()
    seen = set(values)
    previous = env.model.entries[0]
    for i in range(8):
        value = 1 << i if env.spec["kind"] == "byte_mask" else 0xA000 + i
        await env.cycle({i % 3: Write(0, value, True)}, env.queries((previous, value)))
        seen.add(value)
        previous = value
    per_bank = env.spec["size"] // env.spec["banks"]
    for i, address in enumerate((0, per_bank, 2 * per_bank, 3 * per_bank, 0, env.spec["size"] - 1)):
        value = (1 << (i + 8)) | 3 if env.spec["kind"] == "byte_mask" else 0xB000 + i
        old = env.model.entries[address]
        await env.cycle({i % 3: Write(address, value, True)}, env.queries((old, value)))
        seen.add(value)
    await env.idle(env.spec["write_delay"])
    await env.probe_values(seen)
    await env.probe_values()
    # Verify all known entries after a quiet period with changing disabled data.
    for i in range(5):
        poison = {lane: Write((i + lane) % env.spec["size"], 0xFFFF ^ (1 << lane), False) for lane in range(3)}
        await env.cycle(poison, env.queries((previous, 0)))


@pytest.mark.parametrize("seed", (1411, 20261018))
async def test_seeded_legal_parallel_traffic(cam, seed):
    env = cam
    rng = random.Random(seed)
    values = await env.initialize_pool()
    seen = set(values)
    limit = 1 << env.spec["width"]
    for _ in range(600):
        active = rng.sample(range(3), rng.randrange(4))
        addresses = rng.sample(range(env.spec["size"]), len(active))
        writes = {lane: Write(rng.randrange(env.spec["size"]), rng.randrange(limit), False) for lane in range(3)}
        for lane, address in zip(active, addresses, strict=True):
            value = rng.randrange(limit) if rng.random() < 0.6 else rng.choice((0, 1, 3, 6, 0xFFFF))
            writes[lane] = Write(address, value, True)
            seen.add(value)
        queries = []
        for _ in env.spec["queries"]:
            value = rng.choice(env.model.entries) if rng.random() < 0.6 else rng.randrange(limit)
            queries.append(Query(value, bool(rng.randrange(2)) if env.spec["kind"] == "address_line" else False))
        await env.cycle(writes, queries)
    await env.idle(env.spec["write_delay"])
    await env.probe_values(seen)
    await env.probe_values()
    assert all(v is not None for v in env.model.entries)
