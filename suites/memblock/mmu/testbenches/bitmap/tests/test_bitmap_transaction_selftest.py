"""Offline transaction-contract self-checks; no native DUT construction."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.tests.transaction_helpers import Signal
from suites.memblock.mmu.testbenches.bitmap.env.bitmap import BitmapEnv

pytestmark = pytest.mark.selftest


def test_response_snapshot_does_not_expose_live_state():
    env = BitmapEnv.__new__(BitmapEnv)
    env.resp = {name: Signal(value) for name, value in
                (("valid", 1), ("cf", 1), ("id", 7))}
    env.cfs = [Signal(1), Signal(0), Signal(1)]
    snap = env.response_snapshot()
    assert snap == {"valid": 1, "cf": 1, "id": 7, "cfs": [1, 0, 1]}
    snap["cfs"][0] = 0
    snap["valid"] = 0
    assert env.cfs[0].value == 1 and env.resp["valid"].value == 1
    again = env.response_snapshot()
    assert again is not snap and again["cfs"] is not snap["cfs"]
