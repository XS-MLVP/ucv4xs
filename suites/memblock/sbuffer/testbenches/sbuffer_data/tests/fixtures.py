"""SbufferData DUT fixtures, registered by the suite-root conftest."""
from __future__ import annotations

import pytest

from suites.memblock.sbuffer.testbenches.shared.env.native import initialize_inputs
from suites.memblock.sbuffer.testbenches.shared.env.native import load_sbuffer_data_dut
from suites.memblock.sbuffer.testbenches.sbuffer_data.coverage import SbufferDataCoverage
from suites.memblock.sbuffer.testbenches.sbuffer_data.env import SbufferDataEnv


def _finish(dut) -> None:
    """Verilator writes the coverage database during Finish()."""
    dut.Finish()


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
