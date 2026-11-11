"""Refill completion, victim way capture and error reporting."""

from __future__ import annotations

import pytest


@pytest.mark.feature("ICACHE-MISSUNIT-005")
async def test_refill_writes_the_victim_way_the_replacer_chose(missunit_agent):
    agent = missunit_agent
    agent.replacer.way = 0b10
    await agent.submit_fetch(0x6000, 0x70)
    issues = await agent.drain()
    assert len(issues) == 1
    observed = await agent.complete(issues[0])
    assert observed.block == 0x6000
    assert observed.vset == 0x70
    assert observed.waymask == 0b0100, "the refill must target the victim way"
    assert observed.meta_write == 1 and observed.data_write == 1


@pytest.mark.feature("ICACHE-MISSUNIT-005")
async def test_victim_request_names_the_missing_set(missunit_agent):
    agent = missunit_agent
    agent.replacer.way = 0b01
    await agent.submit_prefetch(0x6100, 0x71)
    issues = await agent.drain()
    # drain() already asserts every victim request matches its MSHR's set; the
    # refill must then land in the way the replacer returned for that set.
    observed = await agent.complete(issues[0])
    assert observed.vset == 0x71
    assert observed.waymask == 0b0010


@pytest.mark.feature("ICACHE-MISSUNIT-006")
async def test_response_publishes_the_entry_metadata(missunit_agent):
    agent = missunit_agent
    agent.replacer.way = 0b11
    await agent.submit_fetch(0x6200, 0x72)
    issues = await agent.drain()
    observed = await agent.complete(issues[0])
    assert observed.valid == 1
    assert observed.block == 0x6200 and observed.vset == 0x72
    assert observed.waymask == 0b1000
    assert observed.corrupt == 0 and observed.denied == 0
    assert agent.occupied() == [], "a completed entry must be released"


@pytest.mark.feature("ICACHE-MISSUNIT-006")
async def test_each_refill_uses_its_own_mshr_metadata(missunit_agent):
    """Back-to-back refills must not mix up block/set/way of different entries."""
    agent = missunit_agent
    agent.replacer.way = 0b01
    await agent.submit_fetch(0x6300, 0x73)
    await agent.submit_prefetch(0x6400, 0x74)
    issues = await agent.drain()
    assert len(issues) == 2
    first = await agent.complete(issues[0])
    second = await agent.complete(issues[1])
    assert (first.block, first.vset) == (0x6300, 0x73)
    assert (second.block, second.vset) == (0x6400, 0x74)
    assert first.valid == 1 and second.valid == 1
    assert agent.occupied() == []


@pytest.mark.feature("ICACHE-MISSUNIT-007")
async def test_corrupt_refill_is_reported_but_not_written(missunit_agent):
    agent = missunit_agent
    agent.memory.corrupt = 1
    await agent.submit_fetch(0x6500, 0x75)
    issues = await agent.drain()
    observed = await agent.complete(issues[0])
    assert observed.valid == 1, "the pipeline must learn the refill failed"
    assert observed.corrupt == 1
    assert observed.meta_write == 0, "a corrupt line must not enter the cache"
    assert observed.data_write == 0
    assert agent.occupied() == []


@pytest.mark.feature("ICACHE-MISSUNIT-007")
async def test_denied_refill_is_reported_as_a_write_error(missunit_agent):
    agent = missunit_agent
    agent.memory.denied = 1
    await agent.submit_fetch(0x6600, 0x76)
    issues = await agent.drain()
    observed = await agent.complete(issues[0])
    assert observed.valid == 1
    assert observed.denied == 1
    # TileLink requires corrupt to accompany denied; neither may be cached.
    assert observed.corrupt == 1
    assert observed.meta_write == 0 and observed.data_write == 0


@pytest.mark.feature("ICACHE-MISSUNIT-006")
async def test_refill_of_a_prefetch_also_answers_the_prefetch_pipe(missunit_agent):
    agent = missunit_agent
    agent.replacer.way = 0b10
    await agent.submit_prefetch(0x6700, 0x77)
    issues = await agent.drain()
    observed = await agent.complete(issues[0])
    assert observed.valid == 1
    assert observed.block == 0x6700
    assert observed.meta_write == 1 and observed.data_write == 1
    assert agent.occupied() == []
