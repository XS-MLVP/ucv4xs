"""IfuPerfAnalysis Picker fixtures with toffee-managed coverage.

The DUT is constructed before the managed runner attaches its coverage file,
so each test starts with an explicit (and therefore covered) reset whose first
active cycle is the one after de-assertion.
"""

from __future__ import annotations

import pytest

from suites.frontend.ifu.testbenches.shared.env.agent_runtime import agent_runtime
from suites.frontend.ifu.testbenches.shared.env.harness import DutHarness


@pytest.fixture
def perf_analysis_factory(request, tmp_path, monkeypatch):
    from suites.frontend.ifu.testbenches.perf_analysis.env.agent import PerfAnalysisAgent
    monkeypatch.chdir(tmp_path)
    opened = []

    def create():
        harness = DutHarness('perf_analysis')
        opened.append(harness)
        if getattr(request.config, '_toffee_managed_coverage', None) is not None:
            request.getfixturevalue('toffee_register_dut')(harness.dut)
        return PerfAnalysisAgent(harness)

    try:
        yield create
    finally:
        for harness in opened:
            harness.finish()


@pytest.fixture
async def perf_analysis(request, perf_analysis_factory):
    agent = perf_analysis_factory()
    async with agent_runtime(request, agent):
        await agent.reset()
        yield agent
