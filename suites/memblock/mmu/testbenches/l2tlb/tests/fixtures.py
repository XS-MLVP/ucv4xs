"""Fixture ownership for the l2tlb testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_l2tlb_dut
from suites.memblock.mmu.testbenches.l2tlb.coverage import L2TlbCoverage
from suites.memblock.mmu.testbenches.l2tlb.env.l2tlb import L2TlbEnv


@pytest.fixture
def l2tlb_dut():
    DUT, argv = load_l2tlb_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def l2tlb_coverage():
    return L2TlbCoverage()


@pytest.fixture
def l2tlb_env(l2tlb_dut, l2tlb_coverage):
    return L2TlbEnv(l2tlb_dut, l2tlb_coverage)
