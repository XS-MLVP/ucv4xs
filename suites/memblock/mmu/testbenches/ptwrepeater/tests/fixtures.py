"""Lazy fixture ownership for the ptwrepeater testbench."""
from __future__ import annotations

import pytest


@pytest.fixture
def ptwrepeater_dut():
    from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs, load_ptwrepeater_dut

    DUT, argv = load_ptwrepeater_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def repeater_coverage():
    from suites.memblock.mmu.testbenches.ptwrepeater.coverage import RepeaterCoverage

    return RepeaterCoverage()


@pytest.fixture
def repeater_env(ptwrepeater_dut, repeater_coverage):
    from suites.memblock.mmu.testbenches.ptwrepeater.env.ptw import RepeaterEnv

    return RepeaterEnv(ptwrepeater_dut, repeater_coverage)
