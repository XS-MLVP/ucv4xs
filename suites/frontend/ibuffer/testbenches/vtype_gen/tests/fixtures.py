"""VTypeGen-owned pytest fixtures.

The native factory mechanics live in the shared env because both DUTs use the
same Picker lifecycle; this plugin binds the mechanism to its concrete agent.
"""

from __future__ import annotations

import pytest

from suites.frontend.ibuffer.testbenches.shared.env.fixtures import agent_runtime
from suites.frontend.ibuffer.testbenches.shared.env.fixtures import _factory


@pytest.fixture
def vtype_gen_agent_factory(request, tmp_path, monkeypatch):
    from suites.frontend.ibuffer.testbenches.vtype_gen.env.agent import VTypeGenAgent
    return (yield from _factory(request, tmp_path, monkeypatch,
                                "vtype_gen", VTypeGenAgent))


@pytest.fixture
async def vtype_gen_agent(request, vtype_gen_agent_factory):
    agent = vtype_gen_agent_factory()
    async with agent_runtime(request, agent):
        await agent.reset()
        yield agent
