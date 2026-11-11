"""LoadUnitS4 UT: the load head/tail merge result is forwarded unchanged.

Payloads are typed transactions and observations; the environment binds the
generated ports and compares every contract field, so this file contains no pin
names or field dictionaries.
"""
from __future__ import annotations

import random

import pytest

from suites.memblock.lsu.testbenches.load_s4.coverage import S4_CASES
from suites.memblock.lsu.testbenches.load_s4.coverage import LoadS4Coverage
from suites.memblock.lsu.testbenches.load_s4.env import LoadS4Env
from suites.memblock.lsu.testbenches.load_s4.transactions import blank_payload
from suites.memblock.lsu.testbenches.load_s4.transactions import payload_field_names
from suites.memblock.lsu.testbenches.load_s4.transactions import payload_fields
from suites.memblock.lsu.testbenches.load_s4.transactions import random_payload


@pytest.fixture
def s4(dut_factory):
    dut = dut_factory("load_s4")
    return LoadS4Env(dut, LoadS4Coverage())


def test_valid_follows_the_input(s4):
    idle = s4.evaluate(0, blank_payload(), "idle")
    assert idle.payload.hasException in (0, 1)
    assert idle.valid == 0
    s4.coverage.sample_case("pass.idle_keeps_valid_low")
    valid = s4.evaluate(1, blank_payload(), "valid")
    assert valid.valid == 1
    s4.coverage.sample_case("pass.valid_follows_input")


def test_every_field_is_forwarded_unchanged(s4):
    rng = random.Random(71)
    for vector in range(50):
        s4.evaluate(1, random_payload(rng), f"vector {vector}")
    s4.coverage.sample_case("pass.all_fields_identical")


def test_bits_are_dont_care_when_input_is_invalid(s4):
    rng = random.Random(72)
    for _ in range(10):
        s4.evaluate(0, random_payload(rng), "invalid")
    s4.coverage.sample_case("pass.bits_are_dont_care_when_invalid")


def test_full_width_toggle_of_every_field(s4):
    for name, width in payload_fields():
        for bit in range(width):
            payload = blank_payload().with_field(name, 1 << bit)
            s4.evaluate(1, payload, f"{name} bit {bit}")
        s4.evaluate(1, blank_payload(), f"{name} clear")
    s4.coverage.sample_case("pass.full_width_toggle")


def test_every_cause_bit_is_independently_forwarded(s4):
    causes = [name for name in payload_field_names() if name.startswith("cause_")]
    assert causes, "expected cause bits in the payload"
    for cause in causes:
        payload = blank_payload().with_field(cause, 1)
        got = s4.evaluate(1, payload, cause)
        assert got.payload.field(cause) == 1, cause
        assert all(got.payload.field(other) == 0
                   for other in causes if other != cause),\
            f"{cause} leaked into another cause"
    s4.coverage.sample_case("pass.cause_bits_all_present")


def test_valid_falls_again_after_the_last_beats(s4):
    """Leave the DUT idle so both valid toggle directions are exercised."""
    s4.evaluate(1, blank_payload(), "raise")
    got = s4.evaluate(0, blank_payload(), "drop")
    assert got.valid == 0


def test_case_inventory_is_exact():
    assert len(S4_CASES) == len(set(S4_CASES))
    assert len(S4_CASES) == 6
