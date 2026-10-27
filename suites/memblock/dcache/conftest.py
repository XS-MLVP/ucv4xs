"""Project-wide fixtures and import root for the DCache UT workspace."""
from __future__ import annotations

import os
from pathlib import Path
import random
import shutil
import sys
import tempfile

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dcacheverify.common.dut import initialize_inputs, load_dut  # noqa: E402
from dcacheverify.common import pin_trace  # noqa: E402

# Python-level random tests must be reproducible too, not just the Verilator seed.
TEST_SEED = int(os.environ.get("DCACHE_TEST_RANDOM_SEED", "1"))


@pytest.fixture(scope="session", autouse=True)
def deterministic_test_seed():
    """Seed Python's `random` from DCACHE_TEST_RANDOM_SEED (default 1)."""
    random.seed(TEST_SEED)
    yield TEST_SEED


_SCRATCH_DIR: Path | None = None


def pytest_configure(config) -> None:
    """Give every process its own scratch cwd.

    Picker's generated top still contains a default `$dumpfile`; if a DUT is opened
    with the project directory as cwd it can create `memory-direct.fst` there even
    though the UT never enables tracing.  Running the controller *and* each xdist
    worker in a private temporary directory keeps the project tree clean.
    """
    global _SCRATCH_DIR
    _SCRATCH_DIR = Path(tempfile.mkdtemp(prefix="dcache-pytest-", dir=None))
    os.chdir(_SCRATCH_DIR)


def pytest_unconfigure(config) -> None:
    global _SCRATCH_DIR
    if _SCRATCH_DIR is not None:
        os.chdir(ROOT)
        shutil.rmtree(_SCRATCH_DIR, ignore_errors=True)
        _SCRATCH_DIR = None


@pytest.fixture
def dut_factory(request):
    """Open generated DUTs by key; Finish() is called once each on teardown."""
    opened = []
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
        # Optional runtime record of which pins the bench reads/writes; off unless
        # DCACHE_PIN_TRACE points at a file (see tools/audit_output_fields.py).
        return pin_trace.wrap(dut, key)

    yield _open
    for dut in opened:
        dut.Finish()
    pin_trace.dump()
