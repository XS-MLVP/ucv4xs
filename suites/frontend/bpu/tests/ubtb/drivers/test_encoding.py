"""Transaction-to-pin encoding remains outside architectural testcases."""

from __future__ import annotations

from bpuverify.ubtb.transaction.types import PredictRequest
from bpuverify.ubtb.driver.encoding import _encode_lookup


def test_lookup_encoder_maps_request():
    assert _encode_lookup(PredictRequest(0x8000_1000), valid=1) == {
        "s0_fire": 1,
        "s1_fire": 1,
        "start_pc": 0x4000_0800,
    }


def test_lookup_idle_deasserts_request():
    assert _encode_lookup(None, valid=0) == {
        "s0_fire": 0,
        "s1_fire": 1,
        "start_pc": 0,
    }
