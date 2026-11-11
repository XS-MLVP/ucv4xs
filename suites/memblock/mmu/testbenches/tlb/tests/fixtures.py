"""Fixture ownership for the tlb testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_tlb_dut
from suites.memblock.mmu.testbenches.tlb.coverage import TlbCoverage
from suites.memblock.mmu.testbenches.tlb.env import TlbEnv


@pytest.fixture
def tlb_dut():
    DUT, argv = load_tlb_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def tlb_coverage():
    return TlbCoverage()


@pytest.fixture
def tlb_env(tlb_dut, tlb_coverage):
    return TlbEnv(tlb_dut, tlb_coverage)
