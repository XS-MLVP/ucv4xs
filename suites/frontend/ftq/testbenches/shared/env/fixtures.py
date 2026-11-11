"""Environment fixtures for generated FTQ DUTs."""

from __future__ import annotations
from suites.frontend.ftq import ROOT as _SUITE_ROOT

from datetime import datetime
from datetime import timezone
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Any

import pytest

from suites.frontend.ftq.testbenches.shared.env.harness import Dut


def result_dir(request) -> Path:
    configured = os.environ.get("FTQ_RESULT_DIR")
    if configured:
        root = Path(configured).resolve()
    else:
        managed = request.config.getoption("toffee_output", default=None)
        if managed:
            root = Path(managed).resolve()
        else:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            root = _SUITE_ROOT / "results" / f"local-{stamp}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def coverage_path(directory: Path, dut: str, nodeid: str) -> Path:
    safe = nodeid.replace("::", "-").replace("/", "-").replace(".", "-")
    target = directory / "coverage" / dut / f"{safe}.dat"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


@asynccontextmanager
async def agent_runtime(agent, request=None):
    """Finish a clean body before cleanup; do not duplicate a reported FAIL.

    A passing body (including a swallowed checker error) still requires strict
    finish. Async pytest fixtures need the actual setup/call reports, because
    the body exception is not necessarily thrown back through their yield.
    Independent cleanup failures are never suppressed.
    """
    await agent.start()
    try:
        yield agent
    except BaseException:
        raise
    else:
        reports = {} if request is None else getattr(request.node, '_ftq_reports', {})
        nonpassing = any(reports.get(phase) in {'failed', 'skipped'} for phase in ('setup', 'call'))
        finish = getattr(agent, 'finish', None)
        if finish is not None and not nonpassing:
            await finish()
        sampling_audit = getattr(getattr(agent, 'dut', None), 'check_sampling', None)
        if sampling_audit is not None and not nonpassing:
            sampling_audit()
    finally:
        await agent.aclose()


def agent_fixture(dut_name: str, agent_type: type[Any], *,
                  dut_type: type[Dut] = Dut, max_batch_ticks: int = 512):
    """One function-scoped native DUT, execution, agent and coverage file."""

    @pytest.fixture
    async def fixture(request, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        root = result_dir(request)
        model = dut_type(dut_name, coverage_path(root, dut_name, request.node.nodeid))
        async with model:
            await model.reset()
            agent = agent_type(model)
            async with agent_runtime(agent, request):
                yield agent

    fixture.__name__ = f"{dut_name}_agent"
    return fixture


def agent_factory(dut_name, agent_type, *, dut_type: type[Dut] = Dut):
    """Explicit native lifecycles for controls that intentionally fail a body."""
    @pytest.fixture
    def factory(request, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        serial = 0

        @asynccontextmanager
        async def create():
            nonlocal serial
            serial += 1
            model = dut_type(dut_name, coverage_path(result_dir(request), dut_name,
                                                     f'{request.node.nodeid}-instance-{serial}'))
            if getattr(request.config, '_toffee_managed_coverage', None) is not None:
                request.getfixturevalue('toffee_register_dut')(model.dut)
            async with model:
                await model.reset()
                agent = agent_type(model)
                async with agent_runtime(agent):
                    yield agent

        return create
    factory.__name__ = f'{dut_name}_factory'
    return factory
