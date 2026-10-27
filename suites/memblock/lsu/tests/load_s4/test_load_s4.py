"""LoadUnitS4 UT: the load head/tail merge result is forwarded unchanged."""
from __future__ import annotations

import random

import pytest

from lsuverify.common.passthrough import PassthroughEnv, blank, random_payload
from lsuverify.load_s4.coverage import S4_CASES, LoadS4Coverage
from lsuverify.load_s4.env import FIELDS


@pytest.fixture
def s4(dut_factory):
    dut = dut_factory("load_s4")
    return PassthroughEnv(dut, FIELDS, "io_pipeIn", "io_unalignConcat",
                          LoadS4Coverage())


def test_valid_follows_the_input(s4):
    assert s4.evaluate(0, blank(FIELDS), "idle")["hasException"] in (0, 1)
    assert int(s4.out_valid.value) == 0
    s4.coverage.sample_case("pass.idle_keeps_valid_low")
    s4.evaluate(1, blank(FIELDS), "valid")
    assert int(s4.out_valid.value) == 1
    s4.coverage.sample_case("pass.valid_follows_input")


def test_every_field_is_forwarded_unchanged(s4):
    rng = random.Random(71)
    for vector in range(50):
        s4.evaluate(1, random_payload(rng, FIELDS), f"vector {vector}")
    s4.coverage.sample_case("pass.all_fields_identical")


def test_bits_are_dont_care_when_input_is_invalid(s4):
    rng = random.Random(72)
    for _ in range(10):
        s4.evaluate(0, random_payload(rng, FIELDS), "invalid")
    s4.coverage.sample_case("pass.bits_are_dont_care_when_invalid")


def test_full_width_toggle_of_every_field(s4):
    for name, width in FIELDS.items():
        for bit in range(width):
            payload = blank(FIELDS)
            payload[name] = 1 << bit
            s4.evaluate(1, payload, f"{name} bit {bit}")
        s4.evaluate(1, blank(FIELDS), f"{name} clear")
    s4.coverage.sample_case("pass.full_width_toggle")


def test_every_cause_bit_is_independently_forwarded(s4):
    causes = [name for name in FIELDS if name.startswith("cause_")]
    assert causes, "expected cause bits in the payload"
    for cause in causes:
        payload = blank(FIELDS)
        payload[cause] = 1
        got = s4.evaluate(1, payload, cause)
        assert got[cause] == 1, cause
        assert all(got[c] == 0 for c in causes if c != cause),\
            f"{cause} leaked into another cause"
    s4.coverage.sample_case("pass.cause_bits_all_present")


def test_valid_falls_again_after_the_last_beats(s4):
    """Leave the DUT idle so both valid toggle directions are exercised."""
    s4.evaluate(1, blank(FIELDS), "raise")
    s4.evaluate(0, blank(FIELDS), "drop")
    assert int(s4.out_valid.value) == 0


def test_case_inventory_is_exact():
    assert len(S4_CASES) == len(set(S4_CASES))
    assert len(S4_CASES) == 6
