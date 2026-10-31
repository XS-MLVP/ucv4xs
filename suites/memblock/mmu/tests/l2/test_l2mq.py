"""L2TlbMissQueue and L2TlbPrefetch leaf UT."""
from __future__ import annotations

from suites.memblock.mmu.execution import execution, refresh
from suites.memblock.mmu.l2.missqueue import CAPACITY, MQEntry
from suites.memblock.mmu.l2.l2pf import next_line


# L2MQ-01
async def test_miss_queue_fifo_and_capacity(l2mq_env):
    env = l2mq_env
    async with execution(env):
        await env.reset()
        entries = []
        for index in range(CAPACITY):
            entry = MQEntry(
                vpn=(0x4000 + index * 8) & ((1 << 38) - 1),
                s2xlate=index % 4,
                source=(index // 4) % 4,
                is_llptw=index % 5 == 0,
            )
            entries.append(entry)
            await env.enqueue(entry, f"enqueue {index}")
        assert env.model.full
        assert env.read(env.in_ready) == 0
        assert env.read(env.out_valid) == 1
        for index, entry in enumerate(entries):
            await env.dequeue(f"dequeue {index}", expect=entry)
        assert env.read(env.out_valid) == 0
        assert env.read(env.in_ready) == 1


# L2MQ-02
async def test_miss_queue_flush_clears_all_entries(l2mq_env):
    env = l2mq_env
    async with execution(env):
        await env.reset()
        for index in range(5):
            await env.enqueue(MQEntry(0x5000 + index, index % 4, index % 3, index == 0))
        assert env.read(env.out_valid) == 1
        await env.flush()
        assert env.read(env.out_valid) == 0
        assert env.read(env.in_ready) == 1
        await env.enqueue(MQEntry(0x6000, 3, 3, 1))
        await env.dequeue("after flush", expect=MQEntry(0x6000, 3, 3, 1))


# L2MQ-03
async def test_miss_queue_simultaneous_enqueue_and_dequeue(l2mq_env):
    env = l2mq_env
    async with execution(env):
        await env.reset()
        first = MQEntry(0x7000, 0, 1, 0)
        second = MQEntry(0x7008, 3, 2, 1)
        await env.enqueue(first)
        env._drive_in(1, second)
        env.out_ready.Set(1)
        refresh(env)
        assert env.read(env.in_ready) == 1 and env.read(env.out_valid) == 1
        assert (env.read(env.out_vpn), env.read(env.out_s2),
                env.read(env.out_source), env.read(env.out_llptw)) == (
                    first.vpn, first.s2xlate, first.source, first.is_llptw)
        await env.edge()
        env._drive_in(0)
        env.out_ready.Set(0)
        env.model.dequeue()
        env.model.enqueue(second)
        assert env.read(env.out_valid) == 1
        await env.dequeue("second", expect=second)
        assert env.read(env.out_valid) == 0


# L2MQ-04: input VPN/field bits toggle in both directions through the queue.
async def test_miss_queue_input_bit_patterns(l2mq_env):
    env = l2mq_env
    async with execution(env):
        await env.reset()
        patterns = [
            MQEntry(0, 0, 0, 0),
            MQEntry((1 << 38) - 1, 3, 3, 1),
            MQEntry(0x2AAAAAAAAA, 1, 2, 1),
            MQEntry(0x1555555555, 2, 1, 0),
            MQEntry(0, 0, 0, 0),
        ]
        for index, entry in enumerate(patterns):
            await env.enqueue(entry, f"pattern {index}")
        for entry in patterns:
            await env.dequeue(expect=entry)
        await env.flush()


# L2MQ-05: flush-source bits are exercised; hptwReq/hptwId are hardwired zero.
async def test_miss_queue_flush_source_bits(l2mq_env):
    env = l2mq_env
    async with execution(env):
        await env.reset()
        for signal in env.csr_changed:
            signal.Set(1)
        await env.edge()
        for signal in env.csr_changed:
            signal.Set(0)
        await env.edge()
        await env.enqueue(MQEntry(0xA000, 1, 2, 0))
        await env.flush()
