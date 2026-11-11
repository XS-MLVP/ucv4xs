"""Fixture ownership for the hptw testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_hptw_dut
from suites.memblock.mmu.testbenches.l2tlb.coverage import HptwCoverage
from suites.memblock.mmu.testbenches.hptw.env.hptw import HptwEnv


@pytest.fixture
def hptw_dut():
    DUT, argv = load_hptw_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def hptw_coverage():
    return HptwCoverage()


@pytest.fixture
def hptw_env(hptw_dut, hptw_coverage):
    return HptwEnv(hptw_dut, hptw_coverage)
