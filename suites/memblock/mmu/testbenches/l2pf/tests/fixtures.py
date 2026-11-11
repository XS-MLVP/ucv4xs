"""Fixture ownership for the l2pf testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_l2pf_dut
from suites.memblock.mmu.testbenches.l2tlb.coverage import PFCoverage
from suites.memblock.mmu.testbenches.l2pf.env.l2pf import PFEnv


@pytest.fixture
def l2pf_dut():
    DUT, argv = load_l2pf_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def l2pf_coverage():
    return PFCoverage()


@pytest.fixture
def l2pf_env(l2pf_dut, l2pf_coverage):
    return PFEnv(l2pf_dut, l2pf_coverage)
