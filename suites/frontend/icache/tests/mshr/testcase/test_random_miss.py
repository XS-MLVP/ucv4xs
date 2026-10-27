"""Random miss requests through the single MSHR.

Block addresses, set indices and victim ways are all arbitrary within their
fields, so a random stream of allocate/issue/complete cycles proves the entry
stores and republishes them verbatim.  The reference model checks every
observable step (allocation, acquire address/source, way capture, lookup hits).
"""

from __future__ import annotations

import random

import pytest


@pytest.mark.feature("ICACHE-MSHR-001")
async def test_random_misses_round_trip(mshr_agent):
    agent = mshr_agent
    rng = random.Random(0x3151_DA7A)
    for _ in range(32):
        block = rng.getrandbits(42)
        vset = rng.getrandbits(8)
        way = rng.randrange(4)
        await agent.allocate(block, vset)
        await agent.issue(way)
        # Secondary lookups use both ports; drive unrelated random addresses so
        # the hit comparators see both matching and non-matching values.
        await agent.check_hits((rng.getrandbits(42), rng.getrandbits(8)),
                               (block, vset))
        await agent.complete()
