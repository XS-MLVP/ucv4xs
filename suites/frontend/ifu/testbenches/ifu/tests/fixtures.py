"""IFU top-level Picker fixtures with toffee-managed coverage.

The DUT is constructed before the managed runner attaches its coverage file,
so each test starts with an explicit (and therefore covered) reset whose first
active cycle is the one after de-assertion.
"""

from __future__ import annotations

import pytest

from suites.frontend.ifu.testbenches.shared.env.agent_runtime import agent_runtime
from suites.frontend.ifu.testbenches.shared.env.harness import DutHarness


@pytest.fixture
def ifu_agent_factory(request, tmp_path, monkeypatch):
    from suites.frontend.ifu.testbenches.ifu.env.agent import IfuAgent
    monkeypatch.chdir(tmp_path)
    opened = []

    def create():
        harness = DutHarness('ifu')
        opened.append(harness)
        if getattr(request.config, '_toffee_managed_coverage', None) is not None:
            request.getfixturevalue('toffee_register_dut')(harness.dut)
        return IfuAgent(harness)

    try:
        yield create
    finally:
        for harness in opened:
            harness.finish()


@pytest.fixture
async def ifu_agent(request, ifu_agent_factory):
    agent = ifu_agent_factory()
    async with agent_runtime(request, agent):
        await agent.reset()
        yield agent
