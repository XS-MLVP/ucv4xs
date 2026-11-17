"""Lazy fixture ownership for the ptwfilter testbench."""
from __future__ import annotations

import pytest


@pytest.fixture
def ptwfilter_dut():
    from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs, load_ptwfilter_dut

    DUT, argv = load_ptwfilter_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def filter_coverage():
    from suites.memblock.mmu.testbenches.ptwfilter.coverage import FilterCoverage

    return FilterCoverage()


@pytest.fixture
def filter_env(ptwfilter_dut, filter_coverage):
    from suites.memblock.mmu.testbenches.ptwfilter.env.ptw import FilterEnv

    return FilterEnv(ptwfilter_dut, filter_coverage)
