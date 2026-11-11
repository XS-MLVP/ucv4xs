"""InstrUncacheEntry DUT pytest fixtures, registered by the suite root conftest."""

from __future__ import annotations

import pytest

from suites.frontend.instr_uncache.testbenches.shared.env.fixtures import agent_factory as _factory
from suites.frontend.instr_uncache.testbenches.shared.env.fixtures import agent_runtime


@pytest.fixture
def instr_uncache_entry_agent_factory(request, tmp_path, monkeypatch):
    from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.env.agent import EntryAgent
    return (yield from _factory(request, tmp_path, monkeypatch,
                                     "instr_uncache_entry", EntryAgent))


@pytest.fixture
async def instr_uncache_entry_agent(request, instr_uncache_entry_agent_factory):
    agent = instr_uncache_entry_agent_factory()
    async with agent_runtime(request, agent):
        await agent.reset()
        yield agent
