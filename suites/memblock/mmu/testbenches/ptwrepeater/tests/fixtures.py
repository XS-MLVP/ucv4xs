"""Fixture ownership for the ptwrepeater testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_ptwrepeater_dut
from suites.memblock.mmu.testbenches.shared.env.native import load_ptwfilter_dut
from suites.memblock.mmu.testbenches.l2tlb.coverage import RepeaterCoverage
from suites.memblock.mmu.testbenches.ptwrepeater.env.ptw import RepeaterEnv
from suites.memblock.mmu.testbenches.l2tlb.coverage import FilterCoverage
from suites.memblock.mmu.testbenches.ptwrepeater.env.ptw import FilterEnv


@pytest.fixture
def ptwrepeater_dut():
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
    return RepeaterCoverage()


@pytest.fixture
def repeater_env(ptwrepeater_dut, repeater_coverage):
    return RepeaterEnv(ptwrepeater_dut, repeater_coverage)


@pytest.fixture
def ptwfilter_dut():
    DUT, argv = load_ptwfilter_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def filter_coverage():
    return FilterCoverage()


@pytest.fixture
def filter_env(ptwfilter_dut, filter_coverage):
    return FilterEnv(ptwfilter_dut, filter_coverage)
