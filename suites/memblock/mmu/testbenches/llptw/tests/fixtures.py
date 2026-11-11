"""Fixture ownership for the llptw testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_llptw_dut
from suites.memblock.mmu.testbenches.l2tlb.coverage import LlptwCoverage
from suites.memblock.mmu.testbenches.llptw.env.llptw import LlptwEnv


@pytest.fixture
def llptw_dut():
    DUT, argv, schema_path = load_llptw_dut(with_schema=True)
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut, schema_path
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def llptw_coverage():
    return LlptwCoverage()


@pytest.fixture
def llptw_env(llptw_dut, llptw_coverage):
    dut, schema_path = llptw_dut
    return LlptwEnv(dut, llptw_coverage, schema_path=schema_path)
