"""Project-wide fixtures and import root for the Sbuffer UT workspace."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile

import pytest

pytest_plugins = ("ucv.pytest_selftest",)


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from suites.memblock.sbuffer.native import (
    initialize_inputs,
    load_sbuffer_data_dut,
    load_sbuffer_dut,
)
from suites.memblock.sbuffer.sbuffer.coverage import SbufferCoverage
from suites.memblock.sbuffer.sbuffer.env import SbufferEnv
from suites.memblock.sbuffer.sbuffer_data.coverage import SbufferDataCoverage
from suites.memblock.sbuffer.sbuffer_data.env import SbufferDataEnv


def _finish(dut) -> None:
    """Verilator writes the coverage database during Finish()."""
    dut.Finish()


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


@pytest.fixture
def sbuffer_data_dut():
    DUT, argv = load_sbuffer_data_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    # Tracing is compiled in, but the runtime never calls SetWaveform and no
    # waveform switch is provided; no waveform file is produced.
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def sbuffer_data_coverage():
    # One semantic model for the whole run; contributions from every test are
    # merged by the toffee runner. Sampling is manual and only after checks.
    return SbufferDataCoverage()


@pytest.fixture
def sbuffer_data_env(sbuffer_data_dut, sbuffer_data_coverage):
    return SbufferDataEnv(sbuffer_data_dut, sbuffer_data_coverage)


@pytest.fixture
def sbuffer_dut():
    DUT, argv = load_sbuffer_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    dut.io_sqempty.Set(1)
    dut.io_mshr_store_empty.Set(1)
    try:
        yield dut
    finally:
        _finish(dut)


@pytest.fixture(scope="session")
def sbuffer_coverage():
    return SbufferCoverage()


@pytest.fixture
def sbuffer_env(sbuffer_dut, sbuffer_coverage):
    return SbufferEnv(sbuffer_dut, sbuffer_coverage)
