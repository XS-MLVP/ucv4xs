"""Fixture ownership for the pmp testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_pmp_dut
from suites.memblock.mmu.testbenches.l2tlb.coverage import PmpCoverage
from suites.memblock.mmu.testbenches.pmp.env.pmp import PmpEnv


@pytest.fixture
def pmp_dut():
    DUT, argv = load_pmp_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def pmp_coverage():
    return PmpCoverage()


@pytest.fixture
def env_pmp(pmp_dut, pmp_coverage):
    return PmpEnv(pmp_dut, pmp_coverage)
