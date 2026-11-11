"""IBuffer-owned pytest fixtures.

The native factory mechanics live in the shared env because both DUTs use the
same Picker lifecycle; this plugin binds the mechanism to its concrete agent.
"""

from __future__ import annotations

import pytest

from suites.frontend.ibuffer.testbenches.shared.env.fixtures import agent_runtime
from suites.frontend.ibuffer.testbenches.shared.env.fixtures import _factory


@pytest.fixture
def ibuffer_agent_factory(request, tmp_path, monkeypatch):
    from suites.frontend.ibuffer.testbenches.ibuffer.env.agent import IBufferAgent
    return (yield from _factory(request, tmp_path, monkeypatch,
                                "ibuffer", IBufferAgent))


@pytest.fixture
async def ibuffer_agent(request, ibuffer_agent_factory):
    agent = ibuffer_agent_factory()
    async with agent_runtime(request, agent):
        await agent.reset()
        yield agent
