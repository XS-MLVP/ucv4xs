"""Fixture ownership for the ptwcache testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_ptwcache_dut
from suites.memblock.mmu.testbenches.l2tlb.coverage import PtwCacheCoverage
from suites.memblock.mmu.testbenches.ptwcache.env.ptwcache import PtwCacheEnv


@pytest.fixture
def ptwcache_dut():
    DUT, argv = load_ptwcache_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def ptwcache_coverage():
    return PtwCacheCoverage()


@pytest.fixture
def ptwcache_env(ptwcache_dut, ptwcache_coverage):
    return PtwCacheEnv(ptwcache_dut, ptwcache_coverage)
