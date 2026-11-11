"""Fixture ownership for the l2tlbwrapper testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_l2tlbwrapper_dut
from suites.memblock.mmu.testbenches.l2tlbwrapper.env.l2tlbwrapper import L2TlbWrapperEnv


@pytest.fixture
def l2tlbwrapper_dut():
    DUT, argv = load_l2tlbwrapper_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def l2tlbwrapper_coverage():
    from suites.memblock.mmu.testbenches.l2tlb.coverage import L2TlbWrapperCoverage
    return L2TlbWrapperCoverage()


@pytest.fixture
def l2tlbwrapper_env(l2tlbwrapper_dut, l2tlbwrapper_coverage):
    return L2TlbWrapperEnv(l2tlbwrapper_dut, l2tlbwrapper_coverage)
