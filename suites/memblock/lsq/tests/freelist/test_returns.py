"""Coverage-gap-driven return, ordering, recovery and wraparound scenarios."""
import random

import pytest


async def test_return_latency_and_complete_reuse(freelist):
    env = freelist
    size = env.spec["size"]
    for _ in range(3):
        assert set(await env.exhaust()) == set(range(size))
        assert not (await env.cycle(returns=range(size))).recycled
        assert not (await env.cycle()).recycled
        assert (await env.cycle()).recycled == (0, 1, 2, 3)
        await env.settle_returns()
    # The final return generation also has to be consumed, not just enqueued.
    assert await env.exhaust() == tuple(range(size))
    assert not env.obligations


async def test_each_return_channel_preserves_all_slots_at_wrap(freelist):
    env = freelist
    size = env.spec["size"]
    await env.exhaust()
    for rotation in range(4):
        expected = []
        # Same-channel congestion is allowed to run to completion. Rotating
        # the leading channel moves each channel's returns around the pool.
        for offset in range(4):
            bank = (rotation + offset) % 4
            batch = tuple(range(bank, size, 4))
            await env.cycle(returns=batch)
            await env.settle_returns()
            expected.extend(batch)
        assert await env.exhaust() == tuple(expected)
        assert not env.obligations


async def test_unselected_returns_use_slot_priority_not_notification_age(freelist):
    env = freelist
    await env.exhaust()
    # All four items share a channel. At the second notification, slot 8
    # has already been selected, but older-notified slot 12 is still waiting.
    await env.cycle(returns=(12, 8))
    await env.cycle(returns=(4, 0))
    await env.settle_returns()
    assert await env.exhaust() == (8, 0, 4, 12)
    assert not env.obligations


async def test_capacity_one_then_two_remaining(freelist):
    env = freelist
    while len(env.model.available) > 2:
        await env.cycle(min(env.model.offered, len(env.model.available) - 2))
    await env.idle(1)
    await env.cycle(1)
    await env.idle(1)
    await env.cycle(1)
    await env.idle(3)
    assert not env.model.available


async def test_allocate_while_notifying_and_completing_returns(freelist):
    env = freelist
    for _ in range(3):
        await env.cycle(3)
    await env.cycle(2, returns=(0, 1, 2))
    await env.cycle(1, returns=(3, 4))
    await env.cycle(2, returns=(5, 6))
    await env.cycle(1, returns=(7, 8))
    await env.cycle(returns=sorted(env.model.owned))
    await env.settle_returns()
    got = await env.exhaust()
    assert len(got) == env.spec["size"] and set(got) == set(range(env.spec["size"]))
    assert not env.obligations


@pytest.mark.parametrize("interruption", ("owned", "waiting", "selected"))
async def test_reset_cancels_previous_ownership_and_inflight_returns(freelist, interruption):
    env = freelist
    size = env.spec["size"]
    await env.exhaust()
    if interruption != "owned":
        await env.cycle(returns=range(size))
    if interruption == "selected":
        await env.cycle()
    await env.reset()
    assert await env.exhaust() == tuple(range(size))
    await env.idle(size // 4 + 4)
    assert not env.obligations


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_legal_lifecycles(freelist, seed):
    env = freelist
    rng = random.Random(seed)
    for cycle in range(1200):
        n = rng.randrange(env.model.offered + 1)
        owned = sorted(env.model.owned)
        # Alternating high and low return pressure produces fill/drain waves,
        # followed by bursts and same-channel backlogs without duplicate frees.
        return_pressure = 0.15 if cycle % 80 < 40 else 0.8
        count = rng.randrange(min(len(owned), 12) + 1) if rng.random() < return_pressure else 0
        returns = rng.sample(owned, count)
        masks = [mask for mask in range(8) if mask.bit_count() == n]
        await env.cycle(n, returns=returns, confirmation_mask=rng.choice(masks))
    await env.cycle(returns=sorted(env.model.owned))
    await env.settle_returns()
    got = await env.exhaust()
    assert len(got) == env.spec["size"] and set(got) == set(range(env.spec["size"]))
    assert not env.obligations
