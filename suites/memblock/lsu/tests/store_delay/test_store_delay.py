"""DelayPipeline UT: one-cycle store writeback delay with flush filtering.

Every cycle is compared field-for-field against the independent RobPtr model in
``env.py``; each test then records the semantic behaviour it asserted.
"""
from __future__ import annotations

import random

import pytest

from lsuverify.store_delay.coverage import DelayPipelineCoverage
from lsuverify.store_delay.env import (
    LEVEL_FLUSH,
    LEVEL_FLUSH_AFTER,
    PAYLOAD_FIELDS,
    StoreDelayEnv,
    make_bits,
    no_redirect,
    redirect,
)

VADDR = 0x1234


@pytest.fixture
def dly(dut_factory):
    dut = dut_factory("store_delay")
    env = StoreDelayEnv(dut, DelayPipelineCoverage())
    env.reset()
    return env


def idle(dly, cycles=2):
    for _ in range(cycles):
        dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(), "idle")


def test_reset_clears_valid(dly):
    assert int(dly.out_valid.value) == 0
    dly.coverage.sample_case("delay.reset_clears_valid")


def test_single_beat_is_delayed_exactly_one_cycle(dly):
    rng = random.Random(1)
    bits = make_bits(rng)
    dly.cycle(1, bits, no_redirect(), "drive")
    got = dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(), "hold")
    assert got["valid"] == 1
    for name, width in PAYLOAD_FIELDS.items():
        assert got["bits"][name] == bits[name] & ((1 << width) - 1)
    dly.coverage.sample_case("delay.beat_appears_after_one_cycle")
    dly.coverage.sample_case("delay.field_fidelity")


def test_beat_is_not_repeated(dly):
    bits = make_bits(random.Random(2))
    dly.cycle(1, bits, no_redirect(), "drive")
    assert dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(), "out")["valid"] == 1
    for cycle in range(4):
        assert dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(),
                         f"after {cycle}")["valid"] == 0
    dly.coverage.sample_case("delay.single_beat_not_repeated")
    dly.coverage.sample_case("delay.idle_holds_zero")


def test_back_to_back_beats_keep_order_and_payload(dly):
    rng = random.Random(3)
    beats = [make_bits(rng) for _ in range(3)]
    dly.cycle(1, beats[0], no_redirect(), "beat0")
    got = dly.cycle(1, beats[1], no_redirect(), "beat1")
    assert got["bits"] == {k: beats[0][k] for k in PAYLOAD_FIELDS}
    got = dly.cycle(1, beats[2], no_redirect(), "beat2")
    assert got["bits"] == {k: beats[1][k] for k in PAYLOAD_FIELDS}
    got = dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(), "drain")
    assert got["valid"] == 1
    assert got["bits"] == {k: beats[2][k] for k in PAYLOAD_FIELDS}
    dly.coverage.sample_case("delay.back_to_back_three_beats")


def test_input_beat_is_dropped_when_flushed_this_cycle(dly):
    bits = make_bits(None, uop_robIdx_flag=0, uop_robIdx_value=10,
                     uop_robIdx_isFormer=1)
    dly.cycle(1, bits, redirect(flag=0, value=10, former=1, level=LEVEL_FLUSH),
              "killed input")
    got = dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(), "check")
    assert got["valid"] == 0
    dly.coverage.sample_case("kill.input_same_slot_flush")


def test_input_beat_is_dropped_by_a_flush_after_redirect(dly):
    bits = make_bits(None, uop_robIdx_flag=0, uop_robIdx_value=20,
                     uop_robIdx_isFormer=1)
    dly.cycle(1, bits, redirect(flag=0, value=19, former=1, level=LEVEL_FLUSH_AFTER),
              "flushAfter input")
    assert dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(),
                     "check")["valid"] == 0
    dly.coverage.sample_case("kill.input_after_slot_flush_after")

    # Level=flush with an older target kills the same input as well.
    dly.cycle(1, bits, redirect(flag=0, value=19, former=1, level=LEVEL_FLUSH),
              "flush input")
    assert dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(),
                     "check2")["valid"] == 0
    dly.coverage.sample_case("kill.input_after_slot_flush")


def test_a_beat_occupies_the_output_for_exactly_one_cycle(dly):
    """out.ready is tied high, so the registered beat is consumed immediately."""
    bits = make_bits(None, uop_robIdx_flag=0, uop_robIdx_value=30,
                     uop_robIdx_isFormer=1)
    zero = {name: 0 for name in PAYLOAD_FIELDS}
    assert dly.cycle(1, bits, no_redirect(), "enter")["valid"] == 0
    assert dly.cycle(0, zero, no_redirect(), "visible")["valid"] == 1
    assert dly.cycle(0, zero, no_redirect(), "consumed")["valid"] == 0
    dly.coverage.sample_case("boundary.out_ready_tied_high_consumes_beat_in_one_cycle")


def test_registered_beat_kill_is_not_observable(dut_factory, dly):
    """Differential: the same input stream with and without the output-side
    redirect must produce identical outputs, because out.ready is tied high."""
    streams = []
    for with_redirect in (False, True):
        dut = dut_factory("store_delay")
        env = StoreDelayEnv(dut, dly.coverage)
        env.reset()
        trace = []
        previous_rob = None
        for cycle in range(40):
            # Distinct, monotonically increasing robIdx so a redirect aimed at
            # the registered beat can never also hit this cycle's input.
            rob = 100 + cycle
            bits = make_bits(None, uop_robIdx_flag=0, uop_robIdx_value=rob,
                             uop_robIdx_isFormer=1)
            in_valid = 1 if cycle % 3 == 0 else 0
            redir = no_redirect()
            if with_redirect and previous_rob is not None:
                redir = redirect(flag=0, value=previous_rob, former=1,
                                 level=LEVEL_FLUSH)
            env.drive(in_valid, bits, redir)
            dut.Step(1)
            trace.append((int(env.out_valid.value),
                          *[int(s.value) for s in env.out_bits.values()]))
            previous_rob = rob if in_valid else None
        streams.append(trace)
    assert streams[0] == streams[1], "output-side kill unexpectedly changed the boundary"
    assert any(row[0] for row in streams[0]), "differential stream never produced a beat"
    dly.coverage.sample_case("boundary.registered_beat_kill_is_not_observable")


def test_flush_after_does_not_kill_the_same_slot(dly):
    bits = make_bits(None, uop_robIdx_flag=0, uop_robIdx_value=50,
                     uop_robIdx_isFormer=1)
    dly.cycle(1, bits, no_redirect(), "enter")
    got = dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS},
                    redirect(flag=0, value=50, former=1, level=LEVEL_FLUSH_AFTER),
                    "same slot flushAfter")
    assert got["valid"] == 1
    assert got["bits"] == bits
    dly.coverage.sample_case("level.flush_after_same_slot_survives")


def test_former_bit_orders_the_two_halves_of_one_entry(dly):
    # Latter uop (isFormer=0) is flushed by a redirect pointing at the former
    # half of the same ROB entry.
    latter = make_bits(None, uop_robIdx_flag=0, uop_robIdx_value=60,
                       uop_robIdx_isFormer=0)
    dly.cycle(1, latter, redirect(flag=0, value=60, former=1, level=LEVEL_FLUSH_AFTER),
              "latter killed")
    assert dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(),
                     "check")["valid"] == 0
    dly.coverage.sample_case("former.latter_input_killed_by_former_redirect")

    # The former uop survives a redirect aimed at the latter half.
    former = make_bits(None, uop_robIdx_flag=0, uop_robIdx_value=61,
                       uop_robIdx_isFormer=1)
    dly.cycle(1, former, redirect(flag=0, value=61, former=0, level=LEVEL_FLUSH_AFTER),
              "former survives")
    got = dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(), "check2")
    assert got["valid"] == 1
    assert got["bits"] == former
    dly.coverage.sample_case("former.former_input_survives_latter_redirect")


def test_ring_wrap_inverts_the_value_comparison(dly):
    # Same value, different flag: the flag decides the younger pointer.
    bits = make_bits(None, uop_robIdx_flag=1, uop_robIdx_value=10,
                     uop_robIdx_isFormer=1)
    dly.cycle(1, bits, redirect(flag=0, value=100, former=1, level=LEVEL_FLUSH_AFTER),
              "wrap kill")
    assert dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(),
                     "check")["valid"] == 0
    dly.coverage.sample_case("wrap.flag_direction_flips")

    # Same flag and numerically greater -> younger, killed by flushAfter.
    older = make_bits(None, uop_robIdx_flag=0, uop_robIdx_value=120,
                      uop_robIdx_isFormer=1)
    dly.cycle(1, older, redirect(flag=0, value=119, former=1, level=LEVEL_FLUSH_AFTER),
              "greater kill")
    assert dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(),
                     "check2")["valid"] == 0
    dly.coverage.sample_case("wrap.value_greater_with_same_flag")


def test_invalid_or_younger_redirect_does_not_disturb_beats(dly):
    rng = random.Random(4)
    bits = make_bits(rng, uop_robIdx_flag=0, uop_robIdx_value=70,
                     uop_robIdx_isFormer=1)
    dly.cycle(1, bits, no_redirect(), "enter")
    got = dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS},
                    redirect(flag=0, value=70, former=1, level=LEVEL_FLUSH, valid=0),
                    "invalid redirect")
    assert got["valid"] == 1 and got["bits"] == bits
    dly.coverage.sample_case("redirect.invalid_never_kills")

    # A younger redirect target (strictly after the beat) must not kill it.
    dly.cycle(1, bits, redirect(flag=0, value=71, former=1, level=LEVEL_FLUSH_AFTER),
              "younger target")
    got = dly.cycle(0, {name: 0 for name in PAYLOAD_FIELDS}, no_redirect(), "check")
    assert got["valid"] == 1 and got["bits"] == bits
    dly.coverage.sample_case("redirect.younger_target_never_kills")


def test_seeded_random_stream_matches_reference(dly):
    rng = random.Random(20261025)
    payload = {name: 0 for name in PAYLOAD_FIELDS}
    for cycle in range(600):
        in_valid = 1 if rng.random() < 0.55 else 0
        if in_valid:
            payload = make_bits(
                rng,
                uop_robIdx_flag=rng.randrange(2),
                uop_robIdx_value=rng.randrange(160),
                uop_robIdx_isFormer=rng.randrange(2))
        redir_valid = 1 if rng.random() < 0.35 else 0
        redir = {"valid": redir_valid,
                 "level": rng.randrange(2),
                 "flag": rng.randrange(2),
                 "value": rng.randrange(160),
                 "former": rng.randrange(2)}
        dly.cycle(in_valid, payload, redir, f"random cycle {cycle}")


def test_case_inventory_is_exact():
    from lsuverify.store_delay.coverage import DELAY_CASES
    assert len(DELAY_CASES) == len(set(DELAY_CASES))
    assert len(DELAY_CASES) == 18
