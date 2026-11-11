"""Cross-DUT pytest fixtures for the LSU native workspace.

The keyed loader and input initialisation live in the shared env loader; these
fixtures only own pytest lifetime and working-directory isolation. DUT-specific
fixtures stay in that testbench's tests/ directory.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile

import pytest

from suites.memblock.lsu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.lsu.testbenches.shared.env.native import load_dut


@pytest.fixture(scope="session", autouse=True)
def isolated_workdir():
    """Keep Picker's default $dumpfile out of the project tree."""
    previous = Path.cwd()
    from ucv.runtime import scratch_root
    workdir = Path(tempfile.mkdtemp(prefix="lsu-pytest-", dir=scratch_root()))
    os.chdir(workdir)
    try:
        yield workdir
    finally:
        os.chdir(previous)
        shutil.rmtree(workdir, ignore_errors=True)


@pytest.fixture
def dut_factory(request):
    """Open generated DUTs by key; Finish() is called once each on teardown."""
    opened = []
    # A callable fixture result does not expose DUTs created inside the test
    # body to automatic discovery. Register before Finish() in managed runs.
    managed = getattr(request.config, "_toffee_managed_coverage", None)
    register = request.getfixturevalue("toffee_register_dut") if managed else None

    def _open(key: str):
        DUT, argv = load_dut(key)
        dut = DUT(argv)
        initialize_inputs(dut)
        pins = set(dut.xport.GetKeys())
        if "clock" in pins:
            dut.InitClock("clock")
        if "reset" in pins:
            dut.reset.Set(1)
        opened.append(dut)
        if register is not None:
            register(dut)
        return dut

    yield _open
    for dut in opened:
        dut.Finish()
