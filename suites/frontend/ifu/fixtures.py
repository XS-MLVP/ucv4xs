"""Function-scoped Picker DUT fixtures with toffee-managed coverage.

The DUT is constructed before the managed runner attaches its coverage file,
so each test starts with an explicit (and therefore covered) reset whose first
active cycle is the one after de-assertion.  Coverage discovery recognises the
``dut`` attribute and calls ``Finish`` before native aggregation, which is why
the fixture never hides the generated object inside a private attribute.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import sys

import pytest

from suites.frontend.ifu.harness import DutHarness


@asynccontextmanager
async def agent_runtime(request, agent):
    """Forward an already-reported pytest body outcome into its agent context.

    Async fixtures do not receive the test body's exception at their yield.
    Without this bridge a real checker FAIL is followed by an artificial
    teardown ERROR from strict finish. No verdict is changed here: pytest's
    existing setup/call report is authoritative, independent cleanup errors
    still propagate, and swallowed failures in a passing call still fail finish.
    """
    manager = agent.running()
    await manager.__aenter__()
    try:
        yield agent
    except BaseException:
        if not await manager.__aexit__(*sys.exc_info()):
            raise
    else:
        phases = getattr(request.config, '_ifu_phases', {}).get(request.node.nodeid, {})
        nonpassing = any(phases.get(phase, {}).get('outcome') in {'failed', 'skipped'}
                         for phase in ('setup', 'call'))
        if nonpassing:
            error = RuntimeError('pytest has already reported a nonpassing test body')
            await manager.__aexit__(type(error), error, None)
        else:
            await manager.__aexit__(None, None, None)


@pytest.fixture
def ifu_agent_factory(request, tmp_path, monkeypatch):
    from suites.frontend.ifu.ifu.agent import IfuAgent
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


@pytest.fixture
def uncache_unit_factory(request, tmp_path, monkeypatch):
    from suites.frontend.ifu.uncache_unit.agent import UncacheUnitAgent
    monkeypatch.chdir(tmp_path)
    opened = []

    def create():
        harness = DutHarness('uncache_unit')
        opened.append(harness)
        if getattr(request.config, '_toffee_managed_coverage', None) is not None:
            request.getfixturevalue('toffee_register_dut')(harness.dut)
        return UncacheUnitAgent(harness)

    try:
        yield create
    finally:
        for harness in opened:
            harness.finish()


@pytest.fixture
async def uncache_unit(request, uncache_unit_factory):
    agent = uncache_unit_factory()
    async with agent_runtime(request, agent):
        await agent.reset()
        yield agent


@pytest.fixture
def frontend_trigger_factory(request, tmp_path, monkeypatch):
    from suites.frontend.ifu.frontend_trigger.agent import FrontendTriggerAgent
    monkeypatch.chdir(tmp_path)
    opened = []

    def create():
        harness = DutHarness('frontend_trigger')
        opened.append(harness)
        if getattr(request.config, '_toffee_managed_coverage', None) is not None:
            request.getfixturevalue('toffee_register_dut')(harness.dut)
        return FrontendTriggerAgent(harness)

    try:
        yield create
    finally:
        for harness in opened:
            harness.finish()


@pytest.fixture
async def frontend_trigger(request, frontend_trigger_factory):
    agent = frontend_trigger_factory()
    async with agent_runtime(request, agent):
        await agent.reset()
        yield agent


@pytest.fixture
def instr_boundary_factory(request, tmp_path, monkeypatch):
    from suites.frontend.ifu.instr_boundary.agent import InstrBoundaryAgent
    monkeypatch.chdir(tmp_path)
    opened = []

    def create():
        harness = DutHarness('instr_boundary')
        opened.append(harness)
        if getattr(request.config, '_toffee_managed_coverage', None) is not None:
            request.getfixturevalue('toffee_register_dut')(harness.dut)
        return InstrBoundaryAgent(harness)

    try:
        yield create
    finally:
        for harness in opened:
            harness.finish()


@pytest.fixture
async def instr_boundary(request, instr_boundary_factory):
    agent = instr_boundary_factory()
    async with agent_runtime(request, agent):
        yield agent


@pytest.fixture
def rvc_expander_factory(request, tmp_path, monkeypatch):
    from suites.frontend.ifu.rvc_expander.agent import RvcExpanderAgent
    monkeypatch.chdir(tmp_path)
    opened = []

    def create():
        harness = DutHarness('rvc_expander')
        opened.append(harness)
        if getattr(request.config, '_toffee_managed_coverage', None) is not None:
            request.getfixturevalue('toffee_register_dut')(harness.dut)
        return RvcExpanderAgent(harness)

    try:
        yield create
    finally:
        for harness in opened:
            harness.finish()


@pytest.fixture
async def rvc_expander(request, rvc_expander_factory):
    agent = rvc_expander_factory()
    async with agent_runtime(request, agent):
        yield agent


@pytest.fixture
def pred_checker_factory(request, tmp_path, monkeypatch):
    from suites.frontend.ifu.pred_checker.agent import PredCheckerAgent
    monkeypatch.chdir(tmp_path)
    opened = []

    def create():
        harness = DutHarness('pred_checker')
        opened.append(harness)
        if getattr(request.config, '_toffee_managed_coverage', None) is not None:
            request.getfixturevalue('toffee_register_dut')(harness.dut)
        return PredCheckerAgent(harness)

    try:
        yield create
    finally:
        for harness in opened:
            harness.finish()


@pytest.fixture
async def pred_checker(request, pred_checker_factory):
    agent = pred_checker_factory()
    async with agent_runtime(request, agent):
        await agent.reset()
        yield agent


@pytest.fixture
def perf_analysis_factory(request, tmp_path, monkeypatch):
    from suites.frontend.ifu.perf_analysis.agent import PerfAnalysisAgent
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
