"""Reusable fixture construction; DUT-specific suites declare only metadata."""

from __future__ import annotations

from typing import Any

import pytest
from toffee import Execution
from toffee import XCommClockBackend
from suites.frontend.bpu.testbenches.shared.env.dut import DutFactory


async def close_agent(agent,request,*,checked):
    if checked:
        reports=getattr(request.node,'_bpu_body_reports',{})
        check=not any(reports.get(phase) in {'failed','skipped'} for phase in ('setup','call'))
        await agent.aclose(check=check)
    else:
        await agent.aclose()


@pytest.fixture
def dut_factory(request, tmp_path, monkeypatch):
    # Native $dumpfile is process-cwd relative even when tracing is disabled.
    monkeypatch.chdir(tmp_path)
    managed = bool(request.config.getoption('toffee_output', default=None))
    register = request.getfixturevalue('toffee_register_dut') if managed else None
    factory = DutFactory(managed_coverage=managed, coverage_register=register)
    try:
        yield factory
    finally:
        factory.close()


def agent_fixture(
    dut_name: str,
    agent_type: type[Any],
    *,
    max_batch_ticks: int,
    checked_close: bool = False,
):
    """Create one function-scoped native DUT/Execution/agent fixture."""

    @pytest.fixture
    async def fixture(dut_factory, request):
        coverage_name = f"{request.node.name}-coverage.dat"
        dut = dut_factory.create(dut_name, coverage_name=coverage_name)
        backend = XCommClockBackend(dut.GetXClock())
        try:
            async with Execution(backend, max_batch_ticks=max_batch_ticks) as execution:
                agent = agent_type(dut)
                await agent.start(execution)
                try:
                    yield agent
                finally:
                    await close_agent(agent,request,checked=checked_close)
        finally:
            # Execution releases ownership; its caller owns the backend itself.
            backend.close()

    fixture.__name__ = f"{dut_name}_agent"
    return fixture
