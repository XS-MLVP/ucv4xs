"""Fixture ownership for the tlbn testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_tlbn_dut
from suites.memblock.mmu.testbenches.l2tlb.coverage import TlbnCoverage
from suites.memblock.mmu.testbenches.tlbn.env import TlbNonBlockEnv


@pytest.fixture
def tlbn_dut():
    DUT, argv = load_tlbn_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def tlbn_coverage():
    return TlbnCoverage()


@pytest.fixture
def tlbn_env(tlbn_dut, tlbn_coverage):
    return TlbNonBlockEnv(tlbn_dut, tlbn_coverage)
