"""Arbiter3_StoreStageIO UT: S0 store request-source arbitration.

Covers ARB3-IDLE / TAIL-ONLY / SCALAR-ONLY / PRIORITY / NO-DROP /
SELECT-ISOLATION / EXCV19 / VALID-GATED from
``docs/contracts/store-arbiter.md``.
"""
from __future__ import annotations

import random

import pytest

from lsuverify.store_arbiter.coverage import (
    BEAT_KINDS,
    FIELD_WIDTHS,
    GROUP_FIELDS,
    ISOLATION_CASES,
    SCALAR_GROUPS,
    SHAPES,
    TAIL_GROUPS,
    StoreArbiterCoverage,
)
from lsuverify.store_arbiter.env import (
    BUBBLE,
    IN0_FIELDS,
    IN1_FIELDS,
    StoreArbiterEnv,
    random_payload,
)


@pytest.fixture
def arb(dut_factory):
    dut = dut_factory("store_arbiter")
    return StoreArbiterEnv(dut, StoreArbiterCoverage())


def patterned(fields: dict[str, int], pattern: str) -> dict[str, int]:
    """Deterministic payload shapes used to avoid constant-only comparisons.

    ``walking_bit`` places exactly one set bit across the concatenated payload,
    which is the only correct reading of a walking-one stimulus.
    """
    if pattern == "walking_bit":
        return walking_payload(fields, 0)
    result = {}
    for index, (name, width) in enumerate(fields.items()):
        mask = (1 << width) - 1
        if pattern == "zero":
            value = 0
        elif pattern == "all_ones":
            value = mask
        elif pattern == "mixed":
            value = (0x9E3779B9 * (index + 1) + 0x7F4A7C15) & mask
            if value in (0, mask):
                value = (0x5DEECE66D * (index + 2) + 0xB) & mask
            if value in (0, mask):
                value = mask >> 1 if mask > 1 else 0
        else:
            raise ValueError(pattern)
        result[name] = value
    return result


def walking_payload(fields: dict[str, int], position: int) -> dict[str, int]:
    """Set exactly one bit of the concatenated field vector."""
    total = sum(fields.values())
    position %= total
    result: dict[str, int] = {}
    offset = 0
    for name, width in fields.items():
        if offset <= position < offset + width:
            result[name] = 1 << (position - offset)
        else:
            result[name] = 0
        offset += width
    return result


# ARB3-IDLE: neither source requests; bubble payload is the documented default.
def test_idle_outputs_bubble_and_keeps_scalar_ready(arb):
    arb.drive(False, None, False, None)
    arb.eval()
    observed = arb.check("idle")
    assert observed["valid"] == 0
    assert observed["entrance"] == BUBBLE["entrance"]
    assert observed["ready"] == 1
    # The bubble payload is an exact observable, not merely "don't care".
    for name, want in BUBBLE.items():
        got = int(arb.out[name].value)
        assert got == want, f"bubble field {name} {got:#x} != {want:#x}"


# ARB3-TAIL-ONLY: unalign tail is accepted and propagates field-for-field.
def test_unalign_tail_alone_propagates_every_field(arb):
    payload = patterned(IN0_FIELDS, "mixed")
    arb.drive(True, payload, False, None)
    arb.eval()
    observed = arb.check("tail-only")
    assert observed == {"valid": 1, "ready": 0, "entrance": 0x1}


# ARB3-SCALAR-ONLY: scalar request propagates including ssid/storeSetHit.
def test_scalar_alone_propagates_every_field(arb):
    payload = patterned(IN1_FIELDS, "mixed")
    payload["ssid"] = 0x2A
    payload["storeSetHit"] = 1
    payload["accessType_isCbo"] = 1
    arb.drive(False, None, True, payload)
    arb.eval()
    observed = arb.check("scalar-only")
    assert observed == {"valid": 1, "ready": 1, "entrance": 0x8}
    assert int(arb.out["ssid"].value) == 0x2A
    assert int(arb.out["storeSetHit"].value) == 1


# ARB3-PRIORITY: simultaneous requests select the unalign tail, scalar blocked.
def test_both_valid_selects_tail_and_blocks_scalar(arb):
    tail = patterned(IN0_FIELDS, "all_ones")
    scalar = patterned(IN1_FIELDS, "all_ones")
    scalar["ssid"] = 0x3F
    scalar["storeSetHit"] = 1
    arb.drive(True, tail, True, scalar)
    arb.eval()
    observed = arb.check("both-valid")
    assert observed == {"valid": 1, "ready": 0, "entrance": 0x1}
    # ARB3-SELECT-ISOLATION: scalar-only fields must not leak into a tail beat.
    assert int(arb.out["ssid"].value) == 0
    assert int(arb.out["storeSetHit"].value) == 0


# ARB3-NO-DROP: the tail source has no ready, so it can never be lost.
@pytest.mark.parametrize("scalar_valid", [0, 1])
def test_tail_is_never_dropped_for_any_scalar_state(arb, scalar_valid):
    tail = patterned(IN0_FIELDS, "walking_bit")
    scalar = patterned(IN1_FIELDS, "zero")
    arb.drive(True, tail, bool(scalar_valid), scalar)
    arb.eval()
    observed = arb.check(f"no-drop scalar_valid={scalar_valid}")
    assert observed["valid"] == 1
    assert observed["entrance"] == 0x1


# ARB3-VALID-GATED: gated fields are zero when their source is not selected and
# equal the source value when it is (the reference already encodes both halves).
@pytest.mark.parametrize("shape", ["zero", "all_ones", "mixed", "walking_bit"])
def test_valid_gated_fields_follow_selected_source(arb, shape):
    tail = patterned(IN0_FIELDS, shape)
    scalar = patterned(IN1_FIELDS, shape)
    for in0_valid, in1_valid in ((1, 0), (0, 1), (1, 1)):
        arb.drive(bool(in0_valid), tail, bool(in1_valid), scalar)
        arb.eval()
        arb.check(f"gated shape={shape} in0={in0_valid} in1={in1_valid}")


# ARB3-EXCV19: exceptionVec[19] exists only on the tail source.
def test_exception_vec_19_comes_only_from_tail(arb):
    tail = patterned(IN0_FIELDS, "zero")
    tail["uop_exceptionVec_19"] = 1
    scalar = patterned(IN1_FIELDS, "all_ones")
    arb.drive(True, tail, False, None)
    arb.eval()
    arb.check("exc19 tail selected")
    assert int(arb.out["uop_exceptionVec_19"].value) == 1
    arb.drive(False, None, True, scalar)
    arb.eval()
    arb.check("exc19 scalar selected")
    assert int(arb.out["uop_exceptionVec_19"].value) == 0


# ARB3-SELECT-ISOLATION: mutating the non-selected source cannot change output.
def test_non_selected_source_mutation_never_leaks(arb):
    rng = random.Random(0xA8B3)

    # Case 1: tail selected, scalar mutated -> ssid/storeSetHit stay zero.
    tail = patterned(IN0_FIELDS, "mixed")
    for case in ("scalar_ssid_no_leak", "scalar_storeSetHit_no_leak"):
        field = "ssid" if case == "scalar_ssid_no_leak" else "storeSetHit"
        baseline = None
        for attempt in range(8):
            scalar = random_payload(rng, IN1_FIELDS)
            arb.drive(True, tail, True, scalar)
            arb.eval()
            arb.check(f"isolation {case} attempt {attempt}")
            snapshot = {name: int(signal.value) for name, signal in arb.out.items()}
            if baseline is None:
                baseline = snapshot
                assert snapshot[field] == 0
            else:
                assert snapshot == baseline, f"{case}: output changed with scalar {field}"
        arb.coverage.sample_isolation(case)

    # Case 2: scalar selected, tail payload mutated -> instrType constant,
    # exc19 zero; and the same tail payload is fully visible when re-selected.
    scalar = patterned(IN1_FIELDS, "mixed")
    scalar["accessType_isCbo"] = 0
    for case in ("tail_instrType_constant", "tail_exceptionVec19_no_leak"):
        baseline = None
        for attempt in range(8):
            tail_variant = random_payload(rng, IN0_FIELDS)
            if case == "tail_exceptionVec19_no_leak":
                tail_variant["uop_exceptionVec_19"] = attempt & 1
            else:
                tail_variant["accessType_instrType"] = attempt & 0x7
            arb.drive(False, None, True, scalar)
            arb.eval()
            arb.check(f"isolation {case} attempt {attempt}")
            snapshot = {name: int(signal.value) for name, signal in arb.out.items()}
            if baseline is None:
                baseline = snapshot
                assert snapshot["accessType_instrType"] == 1
                assert snapshot["uop_exceptionVec_19"] == 0
            else:
                assert snapshot == baseline, f"{case}: output changed with tail payload"
            arb.drive(True, tail_variant, False, None)
            arb.eval()
            arb.check(f"{case} tail reselect attempt {attempt}")
        arb.coverage.sample_isolation(case)


# Legit random: independent Bernoulli sources, every beat checked.
def test_seeded_random_traffic_checks_every_beat(arb):
    rng = random.Random(20261025)
    for beat in range(600):
        in0_valid = rng.random() < 0.35
        in1_valid = rng.random() < 0.55
        tail = random_payload(rng, IN0_FIELDS) if in0_valid else None
        scalar = random_payload(rng, IN1_FIELDS) if in1_valid else None
        arb.drive(in0_valid, tail, in1_valid, scalar)
        arb.eval()
        arb.check(f"random beat {beat}")


# Field groups are checked at every declared payload shape for both sources.
@pytest.mark.parametrize("source", ["tail", "scalar"])
@pytest.mark.parametrize("shape", list(SHAPES))
def test_every_group_is_seen_at_every_shape(arb, source, shape):
    fields = IN0_FIELDS if source == "tail" else IN1_FIELDS
    payload = patterned(fields, shape)
    if source == "tail":
        arb.drive(True, payload, False, None)
    else:
        arb.drive(False, None, True, payload)
    arb.eval()
    arb.check(f"group coverage {source} {shape}")
    expected_groups = TAIL_GROUPS if source == "tail" else SCALAR_GROUPS
    assert tuple(GROUP_FIELDS[source]) == tuple(expected_groups)
    for name in fields:
        assert FIELD_WIDTHS[name] == fields[name]


# Walking-one stimulus is extra width coverage; it classifies as "mixed".
@pytest.mark.parametrize("source", ["tail", "scalar"])
def test_walking_one_payload_still_matches_reference(arb, source):
    fields = IN0_FIELDS if source == "tail" else IN1_FIELDS
    total = sum(fields.values())
    for position in (0, 1, total // 2, total - 1):
        payload = walking_payload(fields, position)
        assert sum(bin(value).count("1") for value in payload.values()) == 1
        if source == "tail":
            arb.drive(True, payload, False, None)
        else:
            arb.drive(False, None, True, payload)
        arb.eval()
        arb.check(f"walking-one {source} bit {position}")


def test_contract_inventories_are_exactly_the_declared_sets():
    assert BEAT_KINDS == ("idle_bubble", "tail_only_grant", "scalar_only_grant",
                          "both_tail_priority")
    assert SHAPES == ("zero", "all_ones", "mixed")
    assert set(ISOLATION_CASES) == {
        "scalar_ssid_no_leak", "scalar_storeSetHit_no_leak",
        "tail_instrType_constant", "tail_exceptionVec19_no_leak"}
