"""Fixture ownership for the l2mq testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_l2mq_dut
from suites.memblock.mmu.testbenches.l2tlb.coverage import MQCoverage
from suites.memblock.mmu.testbenches.l2mq.env.missqueue import MQEnv


@pytest.fixture
def l2mq_dut():
    DUT, argv = load_l2mq_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def l2mq_coverage():
    return MQCoverage()


@pytest.fixture
def l2mq_env(l2mq_dut, l2mq_coverage):
    return MQEnv(l2mq_dut, l2mq_coverage)
