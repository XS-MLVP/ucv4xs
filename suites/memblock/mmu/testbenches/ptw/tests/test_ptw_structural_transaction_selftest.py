"""Offline transaction-contract self-checks; no native DUT construction."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.tests.transaction_helpers import Signal, _dut
from suites.memblock.mmu.testbenches.ptw.env.ptw_walker import PtwEnv

pytestmark = pytest.mark.selftest


def test_structural_ptw_response_is_a_named_channel_operation():
    # Same contract on the bitmap response channel: dropping valid must not
    # clear the unrelated cf stress bit.
    bitmap_env = PtwEnv.__new__(PtwEnv)
    bitmap_env.bitmap = {"resp_valid": Signal(), "resp_cf": Signal()}
    bitmap_env.dut = _dut()
    bitmap_env.drive_structural_bitmap_resp(1, cf=1)
    assert (bitmap_env.bitmap["resp_valid"].value,
            bitmap_env.bitmap["resp_cf"].value) == (1, 1)
    bitmap_env.drive_structural_bitmap_resp(0)
    assert (bitmap_env.bitmap["resp_valid"].value,
            bitmap_env.bitmap["resp_cf"].value) == (0, 1)
    # A rejected level must not partially drive the channel: validation runs
    # before any Set, so both valid and the untouched cf keep their values.
    with pytest.raises(ValueError):
        bitmap_env.drive_structural_bitmap_resp(1, cf=2)
    assert (bitmap_env.bitmap["resp_valid"].value,
            bitmap_env.bitmap["resp_cf"].value) == (0, 1)
    with pytest.raises(ValueError):
        bitmap_env.drive_structural_bitmap_resp(2)
    assert (bitmap_env.bitmap["resp_valid"].value,
            bitmap_env.bitmap["resp_cf"].value) == (0, 1)
