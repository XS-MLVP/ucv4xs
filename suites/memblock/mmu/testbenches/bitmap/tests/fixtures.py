"""Lazy fixture ownership for the bitmap testbench."""
from __future__ import annotations

import pytest


@pytest.fixture
def bitmap_dut():
    from suites.memblock.mmu.testbenches.shared.env.native import initialize_inputs, load_bitmap_dut

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
    from suites.memblock.mmu.testbenches.bitmap.coverage import BitmapCoverage

    return BitmapCoverage()


@pytest.fixture
def bitmap_env(bitmap_dut, bitmap_coverage):
    from suites.memblock.mmu.testbenches.bitmap.env.bitmap import BitmapEnv

    return BitmapEnv(bitmap_dut, bitmap_coverage)
