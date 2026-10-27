"""Project-wide fixtures and import root for the LSU UT workspace."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lsuverify.common.dut import initialize_inputs, load_dut  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def isolated_workdir():
    """Keep Picker's default $dumpfile out of the project tree."""
    previous = Path.cwd()
    workdir = Path(tempfile.mkdtemp(prefix="lsu-pytest-", dir=None))
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
