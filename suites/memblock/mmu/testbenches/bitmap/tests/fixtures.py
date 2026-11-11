"""Fixture ownership for the bitmap testbench."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs
from suites.memblock.mmu.testbenches.shared.env.native import load_bitmapcache_dut
from suites.memblock.mmu.testbenches.shared.env.native import load_bitmap_dut
from suites.memblock.mmu.testbenches.l2tlb.coverage import BitmapCacheCoverage
from suites.memblock.mmu.testbenches.bitmap.env.bitmap import BitmapCacheEnv
from suites.memblock.mmu.testbenches.l2tlb.coverage import BitmapCoverage
from suites.memblock.mmu.testbenches.bitmap.env.bitmap import BitmapEnv


@pytest.fixture
def bitmapcache_dut():
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
    return BitmapCacheCoverage()


@pytest.fixture
def bitmapcache_env(bitmapcache_dut, bitmapcache_coverage):
    return BitmapCacheEnv(bitmapcache_dut, bitmapcache_coverage)


@pytest.fixture
def bitmap_dut():
    DUT, argv = load_bitmap_dut()
    dut = DUT(argv)
    dut.InitClock("clock")
    initialize_inputs(dut)
    dut.reset.Set(1)
    try:
        yield dut
    finally:
        dut.Finish()


@pytest.fixture(scope="session")
def bitmap_coverage():
    return BitmapCoverage()


@pytest.fixture
def bitmap_env(bitmap_dut, bitmap_coverage):
    return BitmapEnv(bitmap_dut, bitmap_coverage)
