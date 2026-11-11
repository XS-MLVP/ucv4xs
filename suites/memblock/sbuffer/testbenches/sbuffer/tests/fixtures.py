"""Sbuffer DUT fixtures, registered by the suite-root conftest."""
from __future__ import annotations

import pytest

from suites.memblock.sbuffer.testbenches.shared.env.native import initialize_inputs
from suites.memblock.sbuffer.testbenches.shared.env.native import load_sbuffer_dut
from suites.memblock.sbuffer.testbenches.sbuffer.coverage import SbufferCoverage
from suites.memblock.sbuffer.testbenches.sbuffer.env import SbufferEnv


def _finish(dut) -> None:
    """Verilator writes the coverage database during Finish()."""
    dut.Finish()


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
