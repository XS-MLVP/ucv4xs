"""StdExeUnit UT: scalar/vector store-data routing, SQ data and RS feedback."""
from __future__ import annotations

import random

import pytest

from lsuverify.std_exe_unit.coverage import STD_CASES, StdExeUnitCoverage
from lsuverify.std_exe_unit.env import (
    IN_FIELDS,
    VSTD_FIELDS,
    StdExeUnitEnv,
    blank,
    random_in,
    random_vstd,
)

AMO_BIT = 1 << 18


@pytest.fixture
def std(dut_factory):
    dut = dut_factory("std_exe_unit")
    env = StdExeUnitEnv(dut, StdExeUnitCoverage())
    env.reset()
    return env


def run(std, in_valid=0, in_bits=None, vstd_valid=0, vstd=None, deq=(0, 0, 0),
        context="cycle"):
    return std.cycle(in_valid, in_bits or blank(IN_FIELDS), vstd_valid,
                     vstd or blank(VSTD_FIELDS), deq, context)


def std_in(sq=10, sq_second=0, sq_first=0, fuType=0, fuOpType=0x20,
           src_0=0xDEAD_BEEF_0000_0001, rob=7, former=1, **overrides):
    values = dict(fuType=fuType, fuOpType=fuOpType, src_0=src_0,
                  robIdx_flag=0, robIdx_value=rob, robIdx_isFormer=former,
                  sqIdx_first_flag=sq_first, sqIdx_second_flag=sq_second,
                  sqIdx_value=sq)
    values.update(overrides)
    return values


def vstd_in(fuOpType=0x21, data=0x1122_3344_5566_7788_99AA_BBCC_DDEE_FF00,
            sq=4, sq_second=0, sq_first=0, **overrides):
    values = dict(fuOpType=fuOpType, data=data, sqIdx_first_flag=sq_first,
                  sqIdx_second_flag=sq_second, sqIdx_value=sq)
    values.update(overrides)
    return values


# ------------------------------------------------------------ scalar path
def test_scalar_store_writes_rob_and_sq(std):
    deq = (0, 0, 10)
    got = run(std, 1, std_in(sq=10, rob=7, src_0=0x1234), deq=deq, context="scalar")
    assert got["in_ready"] == 1
    assert got["toRob_valid"] == 1
    assert got["sqData_valid"] == 1
    assert got["atomic_valid"] == 0
    std.coverage.sample_case("valid.scalar_store_writes_back_to_rob")
    std.coverage.sample_case("valid.scalar_store_writes_sq_data")
    std.coverage.sample_case("rob.robidx_fields_pass_through")
    std.coverage.sample_case("sq.scalar_payload_zero_extended_high_half")


def test_illegal_issue_blocks_rob_writeback_but_not_sq_data(std):
    """Outside the physical window `out.toRob.valid` drops; `sqData` follows it,
    so it drops too (the store is not committed from this unit)."""
    deq = (0, 0, 10)
    got = run(std, 1, std_in(sq=9), deq=deq, context="illegal")
    assert got["toRob_valid"] == 0
    assert got["sqData_valid"] == 0
    assert got["atomic_valid"] == 0
    std.coverage.sample_case("valid.illegal_issue_blocks_rob_writeback")


def test_amo_goes_to_the_atomic_port_and_not_to_rob_or_sq(std):
    deq = (0, 0, 10)
    got = run(std, 1, std_in(sq=10, fuType=AMO_BIT, src_0=0xABC), deq=deq,
              context="amo")
    assert got["atomic_valid"] == 1
    assert got["toRob_valid"] == 0
    assert got["sqData_valid"] == 0
    std.coverage.sample_case("valid.amo_goes_to_atomic_port_not_rob")
    std.coverage.sample_case("valid.amo_does_not_write_sq_data")


# ------------------------------------------------------------ vector path
def test_vector_std_wins_and_writes_the_full_payload(std):
    deq = (0, 0, 10)
    payload = 0xFEED_FACE_CAFE_BEEF_0123_4567_89AB_CDEF
    got = run(std, 1, std_in(sq=10), 1, vstd_in(sq=4, data=payload), deq=deq,
              context="vstd")
    assert got["in_ready"] == 0
    assert got["sqData_valid"] == 1
    assert int(std.sq["data"].value) == payload
    assert got["toRob_valid"] == 0
    assert got["atomic_valid"] == 0
    std.coverage.sample_case("valid.vstd_writes_sq_data_with_vector_payload")
    std.coverage.sample_case("valid.vstd_blocks_scalar_ready")
    std.coverage.sample_case("valid.vstd_does_not_write_rob")
    std.coverage.sample_case("valid.vstd_does_not_issue_atomic")
    std.coverage.sample_case("valid.no_rob_writeback_when_vector_std_wins")
    std.coverage.sample_case("sq.vector_payload_uses_full_128_bits")


def test_vector_std_alone_still_blocks_the_scalar_ready(std):
    got = run(std, 0, None, 1, vstd_in(), context="vstd only")
    assert got["in_ready"] == 0
    assert got["sqData_valid"] == 1
    assert got["toRob_valid"] == 0


# ------------------------------------------------------------ SQ window
def test_sq_window_boundaries(std):
    """The window is 64 entries in {second_flag, value} operation space, so with
    deq=(0,0,10) slots 10..63 (second=0) and 0..9 (second=1) are legal."""
    deq = (0, 0, 10)
    for second, value, legal in ((0, 10, True), (0, 63, True), (1, 0, True),
                                 (1, 9, True), (1, 10, False), (0, 9, False),
                                 (0, 0, False)):
        got = run(std, 1, std_in(sq=value, sq_second=second), deq=deq,
                  context=f"sq {second},{value}")
        assert got["toRob_valid"] == (1 if legal else 0), f"{second},{value}"
    std.coverage.sample_case("sq.window_start_and_end")


def test_sq_window_wraps_with_the_flag(std):
    deq = (1, 1, 60)     # start op value 124; end = (0, 0, 60)
    # window = {(first=1, second=1, 60..63)} U {(first=0, second=0, 0..59)}
    cases = (
        (1, 1, 60, True), (1, 1, 63, True),
        (0, 0, 0, True), (0, 0, 59, True),
        (1, 1, 59, False), (0, 0, 60, False), (1, 0, 0, False),
    )
    for first, second, value, legal in cases:
        got = run(std, 1, std_in(sq=value, sq_second=second, sq_first=first),
                  deq=deq, context=f"wrap {first},{second},{value}")
        assert got["toRob_valid"] == (1 if legal else 0), f"{first},{second},{value}"
    std.coverage.sample_case("sq.window_wrap_with_flag")


def test_flag_mismatch_is_illegal(std):
    """A different first_flag puts the store in another wrap generation."""
    deq = (1, 1, 60)
    got = run(std, 1, std_in(sq=60, sq_second=1, sq_first=0), deq=deq,
              context="flag mismatch")
    assert got["toRob_valid"] == 0
    std.coverage.sample_case("sq.flag_mismatch_is_illegal")


# ------------------------------------------------------------ feedback
def test_feedback_is_delayed_one_cycle(std):
    deq = (0, 0, 10)
    run(std, 1, std_in(sq=10), deq=deq, context="issue")
    # The register captured at this edge is visible from the next call on.
    assert int(std.feedback_valid.value) == 1
    assert int(std.feedback_hit.value) == 1
    std.coverage.sample_case("feedback.valid_is_one_cycle_delayed")
    std.coverage.sample_case("feedback.hit_true_for_legal_scalar")
    run(std, 0, deq=deq, context="after")
    assert int(std.feedback_valid.value) == 0


def test_feedback_hit_is_false_for_illegal_issue(std):
    deq = (0, 0, 10)
    run(std, 1, std_in(sq=9), deq=deq, context="illegal")
    assert int(std.feedback_valid.value) == 1
    assert int(std.feedback_hit.value) == 0
    std.coverage.sample_case("feedback.hit_false_for_illegal_scalar")


def test_feedback_hit_is_true_for_amo(std):
    deq = (0, 0, 10)
    run(std, 1, std_in(sq=9, fuType=AMO_BIT), deq=deq, context="amo illegal addr")
    assert int(std.feedback_valid.value) == 1
    assert int(std.feedback_hit.value) == 1, "an AMO is always a hit for the RS"
    std.coverage.sample_case("feedback.hit_true_for_amo")


def test_feedback_hit_holds_while_valid_is_low(std):
    deq = (0, 0, 10)
    run(std, 1, std_in(sq=10), deq=deq, context="hit")
    run(std, 0, deq=deq, context="hold")
    run(std, 0, deq=deq, context="still holding")
    assert int(std.feedback_valid.value) == 0
    assert int(std.feedback_hit.value) == 1, "RegEnable holds the last hit value"
    std.coverage.sample_case("feedback.hit_holds_when_invalid")


def test_idle_is_quiet(std):
    for cycle in range(3):
        got = run(std, 0, context=f"idle {cycle}")
        assert got["toRob_valid"] == 0
        assert got["atomic_valid"] == 0
        assert got["sqData_valid"] == 0
        assert got["in_ready"] == 1
    std.coverage.sample_case("valid.idle_quiet")


# ------------------------------------------------------------ random
def test_seeded_random_traffic_matches_the_reference(std):
    rng = random.Random(20261025)
    for cycle in range(400):
        in_valid = 1 if rng.random() < 0.7 else 0
        values = random_in(rng, sqIdx_value=rng.randrange(64),
                           sqIdx_second_flag=rng.randrange(2),
                           sqIdx_first_flag=rng.randrange(2),
                           fuType=(rng.randrange(2) << 18))
        vstd_valid = 1 if rng.random() < 0.2 else 0
        vpayload = random_vstd(rng)
        deq = (rng.randrange(2), rng.randrange(2), rng.randrange(64))
        run(std, in_valid, values, vstd_valid, vpayload, deq,
            context=f"random {cycle}")


def test_case_inventory_is_exact():
    assert len(STD_CASES) == len(set(STD_CASES))
    assert len(STD_CASES) == 22


def test_futype_full_width_and_amo_bit_position(std):
    """Walk fuType's 32 bits: only bit 18 selects the AMO path, every other bit
    must leave the store in the ROB/SQ path."""
    deq = (0, 0, 10)
    for bit in range(32):
        got = run(std, 1, std_in(sq=10, fuType=1 << bit), deq=deq,
                  context=f"fuType bit {bit}")
        assert got["atomic_valid"] == (1 if bit == 18 else 0), f"bit {bit}"
    run(std, 1, std_in(sq=10, fuType=0), deq=deq, context="clear")


def test_src0_and_vstd_data_full_width(std):
    """Walk the 64-bit scalar data and the 128-bit vector payload."""
    deq = (0, 0, 10)
    for bit in range(64):
        run(std, 1, std_in(sq=10, src_0=1 << bit), deq=deq,
            context=f"src0 bit {bit}")
        run(std, 1, std_in(sq=10, src_0=0), deq=deq, context=f"src0 clear {bit}")
    for bit in range(128):
        run(std, 0, None, 1, vstd_in(data=1 << bit), deq=deq,
            context=f"vstd bit {bit}")
        run(std, 0, None, 1, vstd_in(data=0), deq=deq, context=f"vstd clear {bit}")
