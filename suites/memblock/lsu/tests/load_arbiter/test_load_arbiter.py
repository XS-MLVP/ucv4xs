"""Arbiter7_LoadStageIO UT: five-source fixed-priority load arbitration."""
from __future__ import annotations

import itertools
import random

import pytest

from lsuverify.load_arbiter.coverage import CASES, LoadArbiterCoverage
from lsuverify.load_arbiter.env import (
    FIELD_RULES,
    SOURCES,
    LoadArbiterEnv,
    blank_payload,
    random_payload,
    reference_action,
)


@pytest.fixture
def arb(dut_factory):
    dut = dut_factory("load_arbiter")
    return LoadArbiterEnv(dut, LoadArbiterCoverage())


def run(arb, valid, payload=None, out_ready=1, context="cycle"):
    payload = payload or {}
    arb.drive(valid, payload, out_ready)
    arb.eval()
    return arb.check(context, valid, payload, out_ready)


def all_payload(rng=None):
    if rng is None:
        return {source: blank_payload() for source in SOURCES}
    return {source: random_payload(rng, source) for source in SOURCES}


# ------------------------------------------------------------------ priority
def test_idle_cycle_is_a_bubble(arb):
    got = run(arb, {source: 0 for source in SOURCES}, context="idle")
    assert got["valid"] == 0
    assert got["bits"]["entrance"] == 0x80
    assert got["bits"]["noQuery"] == 1
    arb.coverage.sample_case("arb.bubble")
    arb.coverage.sample_case("entrance.bubble_is_0x80")


@pytest.mark.parametrize("source,case", [
    (0, "arb.single_unalign_tail"), (1, "arb.single_replay_hi"),
    (2, "arb.single_fast_replay"), (3, "arb.single_replay_lo"),
    (5, "arb.single_scalar_issue"),
])
def test_each_source_alone_is_selected(arb, source, case):
    valid = {other: (1 if other == source else 0) for other in SOURCES}
    payload = all_payload(random.Random(100 + source))
    got = run(arb, valid, payload, context=f"single {source}")
    assert got["valid"] == 1
    assert got["chosen"] == source
    arb.coverage.sample_case(case)


def test_every_valid_combination_respects_the_priority_order(arb):
    rng = random.Random(7)
    pairs = 0
    for mask in range(1 << len(SOURCES)):
        valid = {source: (mask >> index) & 1
                 for index, source in enumerate(SOURCES)}
        payload = all_payload(rng)
        for out_ready in (0, 1):
            got = run(arb, valid, payload, out_ready,
                      context=f"mask {mask:05b} ready {out_ready}")
            expect = next((s for s in SOURCES if valid[s]), None)
            assert got["chosen"] == expect
        if sum(valid.values()) >= 2:
            pairs += 1
    assert pairs == 26      # C(5,2)+C(5,3)+C(5,4)+C(5,5)
    arb.coverage.sample_case("arb.adjacent_pairs_all_sources")
    arb.coverage.sample_case("arb.all_five_valid")


# --------------------------------------------------------------------- ready
def test_slot0_ready_follows_out_ready(arb):
    valid = {source: 1 for source in SOURCES}
    run(arb, valid, all_payload(), 1, context="ready high")
    assert int(arb.in_ready[0].value) == 1
    run(arb, valid, all_payload(), 0, context="ready low")
    assert int(arb.in_ready[0].value) == 0
    arb.coverage.sample_case("ready.slot0_follows_out_ready")


def test_lower_slots_are_blocked_by_higher_priority_valid(arb):
    """``in_i.ready = ~OR(valid of every higher-priority slot) & out_ready``:
    slot 0 has no higher slot, so it is always ready when out_ready is high."""
    run(arb, {0: 0, 1: 1, 2: 0, 3: 0, 5: 0}, all_payload(), 1, context="slot1 only")
    assert int(arb.in_ready[0].value) == 1, "slot0 is never blocked"
    assert int(arb.in_ready[1].value) == 1, "no higher valid"
    for source in (2, 3, 5):
        assert int(arb.in_ready[source].value) == 0, f"slot{source} blocked by slot1"
    run(arb, {0: 1, 1: 1, 2: 0, 3: 0, 5: 0}, all_payload(), 1, context="slot0 wins")
    assert int(arb.in_ready[0].value) == 1
    for source in (1, 2, 3, 5):
        assert int(arb.in_ready[source].value) == 0, source
    arb.coverage.sample_case("ready.lower_slots_blocked_by_higher_valid")


def test_out_ready_low_blocks_every_ready(arb):
    for mask in range(1 << len(SOURCES)):
        valid = {source: (mask >> index) & 1
                 for index, source in enumerate(SOURCES)}
        run(arb, valid, all_payload(), 0, context=f"mask {mask:05b} blocked")
        for source in SOURCES:
            assert int(arb.in_ready[source].value) == 0, (mask, source)
    arb.coverage.sample_case("ready.out_ready_low_blocks_everything")


# ----------------------------------------------------------------- entrance
def test_entrance_reencoding_and_passthrough(arb):
    cases = {0: 0x01, 1: 0x02, 3: 0x08, 5: 0x40}
    for source, entrance in cases.items():
        payload = all_payload()
        got = run(arb, {s: (1 if s == source else 0) for s in SOURCES}, payload,
                  context=f"entrance {source}")
        assert got["bits"]["entrance"] == entrance, source
    arb.coverage.sample_case("entrance.constant_reencoding")
    # fastReplay keeps whatever entrance S3 encoded (its low bits are reserved
    # for the fast-replay marker), so the value must pass through unchanged.
    payload = all_payload()
    payload[2]["entrance"] = 0x24
    got = run(arb, {0: 0, 1: 0, 2: 1, 3: 0, 5: 0}, payload, context="entrance pass")
    assert got["bits"]["entrance"] == 0x24
    arb.coverage.sample_case("entrance.fast_replay_passthrough")


# ------------------------------------------------------------------- fields
def test_every_field_of_the_selected_source_matches(arb):
    """Directed per-source sweep: all 43 fields, all 5 sources, 4 payload shapes."""
    rng = random.Random(11)
    for source in SOURCES:
        for shape in ("zero", "ones", "mixed"):
            payload = all_payload()
            if shape == "ones":
                payload[source] = {name: (1 << width) - 1
                                   for name, (width, _a, _d) in FIELD_RULES.items()}
            elif shape == "mixed":
                payload[source] = {name: (0x9E3779B9 * (index + 1)) & ((1 << width) - 1)
                                   for index, (name, (width, _a, _d))
                                   in enumerate(FIELD_RULES.items())}
            else:
                payload[source] = blank_payload()
            run(arb, {s: (1 if s == source else 0) for s in SOURCES}, payload,
                context=f"field source{source} {shape}")
    arb.coverage.sample_case("field.full_through")


def test_slot5_bits_are_gated_but_still_pass_through(arb):
    payload = all_payload()
    for name, (_width, arms, _default) in FIELD_RULES.items():
        if (5, "payload") in [(s, m) for s, m in arms] and FIELD_RULES[name][0] == 1:
            payload[5][name] = 1
    got = run(arb, {0: 0, 1: 0, 2: 0, 3: 0, 5: 1}, payload, context="slot5 gated")
    for name, (width, arms, _default) in FIELD_RULES.items():
        if width == 1 and (5, "payload") in [(s, m) for s, m in arms]:
            assert got["bits"][name] == 1, name
    arb.coverage.sample_case("field.single_bit_gated_slot5")


def test_fields_without_a_slot5_arm_fall_to_their_default(arb):
    payload = all_payload()
    for name in ("uop_exceptionVec_23", "uop_exceptionVec_19", "uop_exceptionVec_15",
                 "uop_exceptionVec_7", "uop_exceptionVec_6", "uncacheReplay",
                 "ncReplay", "mshrId", "replayQueueIdx",
                 "uop_perfDebugInfo_runahead_checkpoint_id"):
        # Force the unselected slot-3 payload to all ones: it must not leak.
        width = FIELD_RULES[name][0]
        payload[3][name] = (1 << width) - 1
    got = run(arb, {0: 0, 1: 0, 2: 0, 3: 0, 5: 1}, payload, context="no slot5 arm")
    for name in ("uop_exceptionVec_23", "uop_exceptionVec_19", "uop_exceptionVec_15",
                 "uop_exceptionVec_7", "uop_exceptionVec_6", "uncacheReplay",
                 "ncReplay", "mshrId", "replayQueueIdx",
                 "uop_perfDebugInfo_runahead_checkpoint_id"):
        assert got["bits"][name] == 0, name
    arb.coverage.sample_case("field.missing_slot5_defaults")


def test_paddr_is_only_meaningful_for_fast_replay(arb):
    payload = all_payload()
    for source in SOURCES:
        payload[source]["paddr"] = 0x1234_5000 + source
    for source in (0, 2):
        got = run(arb, {s: (1 if s == source else 0) for s in SOURCES}, payload,
                  context=f"paddr {source}")
        assert got["bits"]["paddr"] == 0x1234_5000 + source, source
    for source in (1, 3, 5):
        got = run(arb, {s: (1 if s == source else 0) for s in SOURCES}, payload,
                  context=f"paddr {source}")
        assert got["bits"]["paddr"] == 0, source
    got = run(arb, {s: 0 for s in SOURCES}, payload, context="paddr bubble")
    assert got["bits"]["paddr"] == 0
    arb.coverage.sample_case("field.paddr_only_for_fast_replay")


def test_tail_size_is_forced_to_q(arb):
    payload = all_payload()
    for source in SOURCES:
        payload[source]["size"] = 2
    got = run(arb, {0: 1, 1: 0, 2: 0, 3: 0, 5: 0}, payload, context="tail size")
    assert got["bits"]["size"] == 4
    for source in (1, 2, 3, 5):
        got = run(arb, {s: (1 if s == source else 0) for s in SOURCES}, payload,
                  context=f"size {source}")
        assert got["bits"]["size"] == 2, source
    arb.coverage.sample_case("field.size_forced_q_for_tail")


def test_pft_type_is_zero_for_both_replay_sources(arb):
    payload = all_payload()
    for source in SOURCES:
        payload[source]["accessType_pftType"] = 3
    for source, expect in ((0, 3), (1, 0), (2, 3), (3, 0), (5, 3)):
        got = run(arb, {s: (1 if s == source else 0) for s in SOURCES}, payload,
                  context=f"pft {source}")
        assert got["bits"]["accessType_pftType"] == expect, source
    arb.coverage.sample_case("field.pfttype_zero_for_replays")


def test_noquery_special_cases(arb):
    payload = all_payload()
    for source in SOURCES:
        payload[source]["noQuery"] = 0
    # Bubble: the collapsed expression yields 1.
    got = run(arb, {s: 0 for s in SOURCES}, payload, context="nq bubble")
    assert got["bits"]["noQuery"] == 1
    # unalign tail forces 0 regardless of its own bit.
    payload[0]["noQuery"] = 1
    got = run(arb, {0: 1, 1: 0, 2: 0, 3: 0, 5: 0}, payload, context="nq tail")
    assert got["bits"]["noQuery"] == 0
    # fast replay is constant-true in this source, so the pin is 1 even when the
    # test drives 0 (documented as a constant-folded source field).
    got = run(arb, {0: 0, 1: 0, 2: 1, 3: 0, 5: 0}, payload, context="nq fast")
    assert got["bits"]["noQuery"] == 1
    # replay hi / lo / scalar pass their own bit through.
    for source in (1, 3, 5):
        payload[source]["noQuery"] = 1
        got = run(arb, {s: (1 if s == source else 0) for s in SOURCES}, payload,
                  context=f"nq {source}")
        assert got["bits"]["noQuery"] == 1, source
        payload[source]["noQuery"] = 0
        got = run(arb, {s: (1 if s == source else 0) for s in SOURCES}, payload,
                  context=f"nq {source} zero")
        assert got["bits"]["noQuery"] == 0, source
    arb.coverage.sample_case("field.noquery_bubble_and_slot2")


def test_unselected_sources_never_leak(arb):
    rng = random.Random(13)
    for chosen in SOURCES:
        valid = {s: (1 if s == chosen else 0) for s in SOURCES}
        payload = all_payload(random.Random(20 + chosen))
        arb.drive(valid, payload, 1)
        arb.eval()
        baseline = {name: int(signal.value) for name, signal in arb.out_bits.items()}
        arb.check(f"isolation baseline {chosen}", valid, payload, 1)
        for round_index in range(6):
            mutated = dict(payload)
            for other in SOURCES:
                if other != chosen:
                    mutated[other] = random_payload(rng, other)
            arb.drive(valid, mutated, 1)
            arb.eval()
            snapshot = {name: int(signal.value) for name, signal in arb.out_bits.items()}
            assert snapshot == baseline, f"source {chosen} leaked (round {round_index})"
    arb.coverage.sample_case("isolation.unselected_source_mutation")


# -------------------------------------------------------------------- random
def test_seeded_random_traffic(arb):
    rng = random.Random(20261025)
    for beat in range(400):
        valid = {source: (1 if rng.random() < 0.35 else 0) for source in SOURCES}
        payload = all_payload(rng)
        out_ready = 1 if rng.random() < 0.7 else 0
        run(arb, valid, payload, out_ready, context=f"random {beat}")


def test_case_inventory_is_exact():
    assert len(CASES) == len(set(CASES))
    assert len(CASES) == 22
