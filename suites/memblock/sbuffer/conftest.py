"""Project-wide fixtures and import root for the Sbuffer UT workspace."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile

import pytest

pytest_plugins = (
    "ucv.pytest_selftest",
    "suites.memblock.sbuffer.testbenches.sbuffer.tests.fixtures",
    "suites.memblock.sbuffer.testbenches.sbuffer_data.tests.fixtures",
)


ROOT = __import__('suites.memblock.sbuffer', fromlist=['ROOT']).ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def isolated_workdir():
    """Keep Picker's default $dumpfile out of the project tree.

    The generated DUT top unconditionally calls $dumpfile/$dumpvars at time 0.
    Running from a private temporary cwd means even a direct pytest invocation
    cannot create a waveform in the repository.
    """
    previous = Path.cwd()
    from ucv.runtime import scratch_root
    workdir = Path(tempfile.mkdtemp(prefix="sbuffer-pytest-", dir=scratch_root()))
    os.chdir(workdir)
    try:
        yield workdir
    finally:
        os.chdir(previous)
        shutil.rmtree(workdir, ignore_errors=True)
