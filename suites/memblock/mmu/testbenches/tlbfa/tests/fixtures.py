"""Fixture ownership for the tlbfa testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_tlbfa_dut
from suites.memblock.mmu.testbenches.tlbfa.coverage import TlbfaCoverage
from suites.memblock.mmu.testbenches.tlbfa.env import TlbfaEnv


@pytest.fixture
def tlbfa_dut():
    DUT, argv = load_tlbfa_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def tlbfa_coverage():
    return TlbfaCoverage()


@pytest.fixture
def tlbfa_env(tlbfa_dut, tlbfa_coverage):
    return TlbfaEnv(tlbfa_dut, tlbfa_coverage)
