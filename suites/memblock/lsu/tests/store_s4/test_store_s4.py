"""StoreUnitS4 UT: the store head/tail merge result is forwarded unchanged."""
from __future__ import annotations

import random

import pytest

from suites.memblock.lsu.store_s4.coverage import S4_CASES, StoreS4Coverage
from suites.memblock.lsu.store_s4.env import FIELDS, StoreS4Env, random_payload


@pytest.fixture
def s4(dut_factory):
    dut = dut_factory("store_s4")
    return StoreS4Env(dut, StoreS4Coverage())


def blank() -> dict:
    return {name: 0 for name in FIELDS}


def test_valid_follows_the_input(s4):
    assert s4.evaluate(0, blank(), "idle")["hasException"] in (0, 1)
    assert int(s4.out_valid.value) == 0
    s4.coverage.sample_case("pass.idle_keeps_valid_low")
    s4.evaluate(1, blank(), "valid")
    assert int(s4.out_valid.value) == 1
    s4.coverage.sample_case("pass.valid_follows_input")


def test_every_field_is_forwarded_unchanged(s4):
    rng = random.Random(41)
    for vector in range(50):
        payload = random_payload(rng)
        s4.evaluate(1, payload, f"vector {vector}")
    s4.coverage.sample_case("pass.all_fields_identical")


def test_bits_are_dont_care_when_input_is_invalid(s4):
    """With valid=0 the DUT must not claim a beat; the payload is not compared."""
    rng = random.Random(42)
    for _ in range(10):
        s4.evaluate(0, random_payload(rng), "invalid")
    s4.coverage.sample_case("pass.bits_are_dont_care_when_invalid")


def test_full_width_toggle_of_every_field(s4):
    for name, width in FIELDS.items():
        for bit in range(width):
            payload = {field: 0 for field in FIELDS}
            payload[name] = 1 << bit
            s4.evaluate(1, payload, f"{name} bit {bit}")
        s4.evaluate(1, {field: 0 for field in FIELDS}, f"{name} clear")
    s4.coverage.sample_case("pass.full_width_toggle")


def test_valid_falls_again_after_the_last_beats(s4):
    """Leave the DUT in the idle state so both valid toggle directions are seen."""
    s4.evaluate(1, {name: 0 for name in FIELDS}, "raise")
    s4.evaluate(0, {name: 0 for name in FIELDS}, "drop")
    assert int(s4.out_valid.value) == 0


def test_case_inventory_is_exact():
    assert len(S4_CASES) == len(set(S4_CASES))
    assert len(S4_CASES) == 5
