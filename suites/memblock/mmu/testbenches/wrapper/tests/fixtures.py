"""Fixture ownership for the wrapper testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_wrapper_dut
from suites.memblock.mmu.testbenches.wrapper.coverage import WrapperCoverage
from suites.memblock.mmu.testbenches.wrapper.env import WrapperEnv


@pytest.fixture
def wrapper_dut():
    DUT, argv = load_wrapper_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def wrapper_coverage():
    return WrapperCoverage()


@pytest.fixture
def wrapper_env(wrapper_dut, wrapper_coverage):
    return WrapperEnv(wrapper_dut, wrapper_coverage)
