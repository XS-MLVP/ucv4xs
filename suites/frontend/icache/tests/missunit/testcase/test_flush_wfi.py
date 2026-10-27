"""Flush, fence.i and WFI behaviour of the miss unit."""

from __future__ import annotations

import pytest


@pytest.mark.feature("ICACHE-MISSUNIT-008")
async def test_flush_drops_prefetch_but_keeps_fetch(missunit_agent):
    agent = missunit_agent
    await agent.submit_fetch(0x7000, 0x80)
    await agent.submit_prefetch(0x7100, 0x81)
    assert len(agent.occupied()) == 2
    await agent.flush()
    occupied = agent.occupied()
    assert len(occupied) == 1, f"only the prefetch may be dropped, still {occupied}"
    assert occupied[0] < agent.model.fetch_mshrs
    # The surviving fetch must still be able to issue and complete.
    issues = await agent.drain()
    assert [issue.source for issue in issues] == occupied
    observed = await agent.complete(issues[0])
    assert observed.valid == 1


@pytest.mark.feature("ICACHE-MISSUNIT-008")
async def test_flush_does_not_release_issued_prefetch_transaction(missunit_agent):
    agent = missunit_agent
    await agent.submit_prefetch(0x7200, 0x82)
    issues = await agent.drain()
    await agent.flush()
    entry = agent.model.entries[issues[0].source]
    assert entry.valid == 1 and entry.issued == 1, (
        "a prefetch already on the memory channel must not be dropped")
    observed = await agent.complete(issues[0])
    assert observed.valid == 0, "a redirected refill must not reach the pipeline"
    assert observed.meta_write == 0 and observed.data_write == 0
    assert agent.occupied() == []


@pytest.mark.feature("ICACHE-MISSUNIT-009")
async def test_fencei_drops_both_pools(missunit_agent):
    agent = missunit_agent
    await agent.submit_fetch(0x7300, 0x83)
    await agent.submit_prefetch(0x7400, 0x84)
    await agent.fencei()
    assert agent.occupied() == [], "fence.i must clear both pools"


@pytest.mark.feature("ICACHE-MISSUNIT-009")
async def test_fencei_keeps_an_issued_entry_until_it_completes(missunit_agent):
    """An already-issued memory transaction must not be leaked."""
    agent = missunit_agent
    await agent.submit_fetch(0x7500, 0x85)
    issues = await agent.drain()
    await agent.fencei()
    entry = agent.model.entries[issues[0].source]
    assert entry.valid == 1 and entry.issued == 1
    observed = await agent.complete(issues[0])
    assert observed.valid == 0, (
        "a line fetched before fence.i may be stale and must not be published")
    assert observed.meta_write == 0 and observed.data_write == 0
    assert agent.occupied() == []


@pytest.mark.feature("ICACHE-MISSUNIT-010")
async def test_wfi_safe_tracks_issued_requests(missunit_agent):
    agent = missunit_agent
    assert agent.wfi_safe() == 1, "an idle miss unit is WFI safe"
    await agent.submit_fetch(0x7600, 0x86)
    assert agent.wfi_safe() == 1, "an unissued miss cannot block WFI"
    issues = await agent.drain()
    assert agent.wfi_safe() == 0, "an issued miss blocks WFI"
    await agent.complete(issues[0])
    assert agent.wfi_safe() == 1, "completion must restore WFI safety"


@pytest.mark.feature("ICACHE-MISSUNIT-010")
async def test_wfi_request_blocks_issuing(missunit_agent):
    agent = missunit_agent
    await agent.submit_fetch(0x7700, 0x87)
    await agent.set_wfi(1)
    for _ in range(6):
        await agent._edge()
        agent.model.step()
        assert agent.acquire_valid() == 0, "a pending WFI request must hold the acquire"
    await agent.set_wfi(0)
    issues = await agent.drain()
    assert len(issues) == 1, "the held request must issue once WFI is released"


