"""Lazy fixture ownership for the bitmapcache testbench."""
from __future__ import annotations

import pytest


@pytest.fixture
def bitmapcache_dut():
    from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs, load_bitmapcache_dut

    DUT, argv = load_bitmapcache_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def bitmapcache_coverage():
    from suites.memblock.mmu.testbenches.bitmapcache.coverage import BitmapCacheCoverage

    return BitmapCacheCoverage()


@pytest.fixture
def bitmapcache_env(bitmapcache_dut, bitmapcache_coverage):
    from suites.memblock.mmu.testbenches.bitmapcache.env.bitmap import BitmapCacheEnv

    return BitmapCacheEnv(bitmapcache_dut, bitmapcache_coverage)
