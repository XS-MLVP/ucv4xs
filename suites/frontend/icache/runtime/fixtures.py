"""Reusable fixture construction; DUT-specific suites declare only metadata."""

from __future__ import annotations

from typing import Any

import pytest
from toffee import Execution
from toffee import XCommClockBackend
from suites.frontend.icache.runtime.dut import DutFactory


async def close_checked_agent(agent, request, *, body_failed=False):
    """Reported non-PASS bodies only clean up; missing/PASS reports must finish.

    Async pytest yields do not normally receive the call exception. Keep the
    report bridge explicit, and retain an independent cleanup error even when
    the body/checker was already reported as a failure.
    """
    reports = getattr(request.node, '_icache_body_reports', {})
    nonpassing = body_failed or any(reports.get(phase) in {'failed', 'skipped'}
                                   for phase in ('setup', 'call'))
    errors = []
    if not nonpassing:
        try:
            await agent.finish()
        except BaseException as error:
            errors.append(error)
    try:
        await agent.aclose()
    except BaseException as error:
        if not any(error is previous for previous in errors):
            errors.append(error)
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise BaseExceptionGroup('ICache finish and independent cleanup errors', errors)


@pytest.fixture
def dut_factory(request, tmp_path, monkeypatch):
    # Keep the generated native default dumpfile out of the source tree.
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
    checked: bool = False,
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
                body_failed = False
                try:
                    yield agent
                except BaseException:
                    body_failed = True
                    raise
                finally:
                    if checked:
                        await close_checked_agent(agent, request, body_failed=body_failed)
                    else:
                        await agent.aclose()
        finally:
            # Execution releases ownership; its caller owns the backend itself.
            backend.close()

    fixture.__name__ = f"{dut_name}_agent"
    return fixture
