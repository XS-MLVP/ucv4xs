"""Random refill addresses and line data across the whole MSHR pool.

Each MSHR owns a block address, set index and a 256-bit D-channel register.
Random legal refills fill all fourteen slots (four fetch, ten prefetch) with
unrelated addresses and random line data; the model still checks allocation
order, acquire source, victim set and every observable response field, so the
random payload cannot hide a control mistake.
"""

from __future__ import annotations

import random

import pytest


@pytest.mark.feature("ICACHE-MISSUNIT-002")
async def test_random_refills_fill_every_mshr(missunit_agent):
    agent = missunit_agent
    rng = random.Random(0x3151_1A0C)
    for _ in range(8):
        # Every victim way is a legal replacer answer; rotating it toggles the
        # way/victimWay payload as well as the two-bit way field.
        agent.replacer.way = rng.randrange(4)
        blocks = []
        for index in range(4):
            block = rng.getrandbits(42)
            vset = rng.getrandbits(8)
            blocks.append((block, vset))
            await agent.submit_fetch(block, vset)
        for index in range(10):
            block = rng.getrandbits(42)
            vset = rng.getrandbits(8)
            blocks.append((block, vset))
            await agent.submit_prefetch(block, vset)
        issues = await agent.drain()
        assert len(issues) == 14, f"only {len(issues)} MSHRs issued"
        assert {issue.block for issue in issues} == {block for block, _ in blocks}
        for issue in issues:
            await agent.complete(issue, data=rng.getrandbits(256))
        assert agent.occupied() == []


@pytest.mark.feature("ICACHE-MISSUNIT-002")
async def test_duplicate_detection_uses_every_mshr_and_both_ports(missunit_agent):
    """A duplicate on the fetch *and* the prefetch stream must be suppressed.

    Every MSHR owns two lookup comparators (fetch and prefetch request); issuing
    a duplicate against each occupied slot exercises all of them, not only the
    first allocated slot.
    """
    agent = missunit_agent
    rng = random.Random(0x3151_D0B1)
    entries = []
    for _ in range(4):
        block, vset = rng.getrandbits(42), rng.getrandbits(8)
        entries.append((block, vset))
        await agent.submit_fetch(block, vset)
    for _ in range(10):
        block, vset = rng.getrandbits(42), rng.getrandbits(8)
        entries.append((block, vset))
        await agent.submit_prefetch(block, vset)
    assert len(agent.occupied()) == 14

    for block, vset in entries:
        before = len(agent.occupied())
        await agent.submit_fetch(block, vset)
        assert len(agent.occupied()) == before, "fetch duplicate allocated"
        await agent.submit_prefetch(block, vset)
        assert len(agent.occupied()) == before, "prefetch duplicate allocated"

    issues = await agent.drain()
    assert len(issues) == 14
    for issue in issues:
        await agent.complete(issue)
    assert agent.occupied() == []


@pytest.mark.feature("ICACHE-MISSUNIT-009")
async def test_both_pools_are_usable_after_fencei(missunit_agent):
    """fence.i must leave every MSHR reusable, not stuck in a flush state."""
    agent = missunit_agent
    rng = random.Random(0x3151_F3C1)
    for _ in range(4):
        await agent.submit_fetch(rng.getrandbits(42), rng.getrandbits(8))
    for _ in range(10):
        await agent.submit_prefetch(rng.getrandbits(42), rng.getrandbits(8))
    await agent.fencei()
    assert agent.occupied() == []
    # Refill the whole pool again: each MSHR's sticky fence.i state must clear.
    for _ in range(4):
        await agent.submit_fetch(rng.getrandbits(42), rng.getrandbits(8))
    for _ in range(10):
        await agent.submit_prefetch(rng.getrandbits(42), rng.getrandbits(8))
    issues = await agent.drain()
    assert len(issues) == 14
    for issue in issues:
        await agent.complete(issue)
    assert agent.occupied() == []
