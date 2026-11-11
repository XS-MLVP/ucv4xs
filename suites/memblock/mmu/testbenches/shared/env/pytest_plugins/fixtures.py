"""Session workdir isolation shared by every MMU testbench."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_workdir():
    """Keep Picker's generated dumpfile out of the evidence tree."""
    previous = Path.cwd()
    from ucv.runtime import scratch_root
    workdir = Path(tempfile.mkdtemp(prefix="mmu-pytest-", dir=scratch_root()))
    os.chdir(workdir)
    try:
        yield workdir
    finally:
        os.chdir(previous)
        shutil.rmtree(workdir, ignore_errors=True)
