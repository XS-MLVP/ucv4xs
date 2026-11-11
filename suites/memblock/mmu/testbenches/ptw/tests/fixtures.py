"""Fixture ownership for the ptw testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_ptw_dut
from suites.memblock.mmu.testbenches.l2tlb.coverage import PtwCoverage
from suites.memblock.mmu.testbenches.ptw.env.ptw_walker import PtwEnv


@pytest.fixture
def ptw_dut():
    DUT, argv, schema_path = load_ptw_dut(with_schema=True)
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut, schema_path
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def ptw_coverage():
    return PtwCoverage()


@pytest.fixture
def ptw_env(ptw_dut, ptw_coverage):
    dut, schema_path = ptw_dut
    return PtwEnv(dut, ptw_coverage, schema_path=schema_path)
