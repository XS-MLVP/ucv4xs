"""MSHR lifecycle: allocate, secondary lookup, issue, complete.

The reference is the standard MSHR contract: one outstanding block, a hit only
for the same block *and* set, the replacement way captured at issue, and bypass
information published while the entry is live.
"""

from __future__ import annotations

import pytest

BLOCK = 0x1234
VSET = 0x10
OTHER_BLOCK = 0x1280
OTHER_SET = VSET ^ 1


@pytest.mark.feature("ICACHE-MSHR-001")
async def test_second_request_is_refused_while_the_entry_is_live(mshr_agent):
    agent = mshr_agent
    await agent.allocate(BLOCK, VSET)
    assert agent.req_ready() == 0, "a live MSHR must refuse a second block"
    await agent.complete()
    assert agent.req_ready() == 1, "a completed MSHR must accept the next block"


@pytest.mark.feature("ICACHE-MSHR-002")
async def test_lookup_requires_both_block_and_set(mshr_agent):
    agent = mshr_agent
    await agent.allocate(BLOCK, VSET)
    assert await agent.check_hits((BLOCK, VSET), (BLOCK, OTHER_SET)) == (1, 0), (
        "only the same block in the same set is a secondary hit")
    assert await agent.check_hits((OTHER_BLOCK, VSET), (BLOCK, VSET)) == (0, 1)


@pytest.mark.feature("ICACHE-MSHR-003")
async def test_victim_way_is_captured_when_the_acquire_fires(mshr_agent):
    agent = mshr_agent
    await agent.allocate(BLOCK, VSET)
    assert agent.info_way() == 0, "an unissued request has no captured way yet"
    await agent.issue(victim_way=0b10)
    assert agent.model.state.way == 0b10, "the way is sampled on the issuing edge"
    assert agent.info_way() == 0b10, "the published way is the captured one"


@pytest.mark.feature("ICACHE-MSHR-004")
async def test_bypass_information_follows_the_live_entry(mshr_agent):
    agent = mshr_agent
    await agent.allocate(BLOCK, VSET)
    assert agent.info_valid() == 1
    assert agent.info_block() == BLOCK
    await agent.issue(victim_way=0b01)
    assert agent.info_valid() == 1, "an issued entry still publishes refill data"
    assert agent.info_way() == 0b01


@pytest.mark.feature("ICACHE-MSHR-008")
async def test_completion_frees_the_entry(mshr_agent):
    agent = mshr_agent
    await agent.allocate(BLOCK, VSET)
    await agent.issue(victim_way=0b01)
    await agent.complete()
    assert agent.info_valid() == 0, "a completed entry publishes nothing"
    assert agent.req_ready() == 1, "a completed entry accepts the next block"
    assert await agent.check_hits((BLOCK, VSET)) == (0, 0), "a freed entry is not a hit target"
    await agent.allocate(OTHER_BLOCK, OTHER_SET)
    assert await agent.check_hits((OTHER_BLOCK, OTHER_SET)) == (1, 0)
