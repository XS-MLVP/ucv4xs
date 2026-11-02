"""Project-wide fixtures and import root for the DCache UT workspace."""
from __future__ import annotations

import os
from pathlib import Path
import random
import shutil
import sys
import tempfile

import pytest

pytest_plugins = ("ucv.pytest_selftest",)


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from suites.memblock.dcache.native import initialize_inputs, load_dut  # noqa: E402
from suites.memblock.dcache import pin_trace  # noqa: E402

# Python-level random tests must be reproducible too, not just the Verilator seed.
TEST_SEED = int(os.environ.get("DCACHE_TEST_RANDOM_SEED", "1"))


@pytest.fixture(scope="session", autouse=True)
def deterministic_test_seed():
    """Seed Python's `random` from DCACHE_TEST_RANDOM_SEED (default 1)."""
    random.seed(TEST_SEED)
    yield TEST_SEED


@pytest.fixture(scope="session", autouse=True)
def isolated_workdir():
    """Change cwd only after worker collection, for native test execution.

    Picker's generated top still contains a default `$dumpfile`; if a DUT is opened
    with the project directory as cwd it can create `memory-direct.fst` there even
    though the UT never enables tracing. Changing the controller cwd in
    pytest_configure makes xdist workers start in scratch and silently lose
    default testpaths. A session fixture runs only in executing workers, after
    collection, and restores the invocation directory even on test failures.
    """
    from ucv.runtime import scratch_root
    previous = Path.cwd()
    workdir = Path(tempfile.mkdtemp(prefix="dcache-pytest-", dir=scratch_root()))
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


@pytest.fixture(params=("dcache","dcache_wrapper"))
def cache_protocol_env(request,dut_factory):
    """The same transport contract through the cache and its real wrapper."""
    from suites.memblock.dcache.dcache.env import DcacheEnv
    from suites.memblock.dcache.dcache_wrapper.env import DcacheWrapperEnv
    env_type=DcacheWrapperEnv if request.param=="dcache_wrapper" else DcacheEnv
    env=env_type(dut_factory(request.param))
    env.reset()
    return env
