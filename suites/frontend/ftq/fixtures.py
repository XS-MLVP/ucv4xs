"""Environment fixtures for generated FTQ DUTs."""

from __future__ import annotations
from suites.frontend.ftq import ROOT as _SUITE_ROOT

from datetime import datetime
from datetime import timezone
import os
from pathlib import Path
from typing import Any

import pytest

from suites.frontend.ftq.harness import Dut


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


def agent_fixture(dut_name: str, agent_type: type[Any], *, max_batch_ticks: int = 512):
    """One function-scoped native DUT, execution, agent and coverage file."""

    @pytest.fixture
    async def fixture(request, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        root = result_dir(request)
        model = Dut(dut_name, coverage_path(root, dut_name, request.node.nodeid))
        async with model:
            await model.reset()
            agent = agent_type(model)
            await agent.start()
            try:
                yield agent
            finally:
                await agent.aclose()

    fixture.__name__ = f"{dut_name}_agent"
    return fixture
