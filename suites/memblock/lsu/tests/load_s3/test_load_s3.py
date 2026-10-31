"""LoadUnitS3 UT: head/tail merge, writeback, LQ update, replay and revoke."""
from __future__ import annotations

import random

import pytest

from suites.memblock.lsu.load_s3.coverage import CASES, LoadS3Coverage
from suites.memblock.lsu.load_s3.env import (
    CAUSE_OH,
    CONCAT_FIELDS,
    EXC_BITS,
    LQWRITE_FIELDS,
    PIPEIN_FIELDS,
    LoadS3Env,
    blank_inputs,
    random_inputs,
)

SCALAR = 0x40
REPLAY_HI = 0x02
TAIL_LANE = 0x01


@pytest.fixture
def s3(dut_factory):
    dut = dut_factory("load_s3")
    env = LoadS3Env(dut, LoadS3Coverage())
    env.reset()
    return env


# ------------------------------------------------------------------- helpers
def pipe(**overrides):
    bits = {name: 0 for name in PIPEIN_FIELDS}
    bits.update({
        "entrance": SCALAR, "accessType_instrType": 1, "mask": 0x00FF,
        "paddr": 0x1234_5000, "uop_robIdx_value": 16, "uop_pdest": 7,
        "uop_fuOpType": 0x06, "shouldWakeup": 1, "shouldWriteback": 1,
        "uop_lqIdx_flag": 0, "uop_lqIdx_value": 3,
    })
    bits.update(overrides)
    return bits


def concat(**overrides):
    bits = {name: 0 for name in CONCAT_FIELDS}
    bits.update(overrides)
    return bits


def make(load=None, concat_bits=None, concat_valid=0, redirect=None,
         tail_valid=0, fast_ready=1, rar_valid=0, rar_nuke=0, ldld=0):
    inputs = blank_inputs()
    if load is not None:
        inputs["pipeIn"]["valid"] = 1
        inputs["pipeIn"]["bits"] = load
    inputs["concat"]["valid"] = concat_valid
    if concat_bits is not None:
        inputs["concat"]["bits"] = concat_bits
    if redirect is not None:
        inputs["redirect"]["valid"] = 1
        inputs["redirect"]["bits"] = redirect
    inputs["unalignTailValid"] = tail_valid
    inputs["fastReplayReady"] = fast_ready
    inputs["rarResp"] = {"valid": rar_valid, "nuke": rar_nuke}
    inputs["ldldCheck"] = ldld
    return inputs


def run(s3, inputs, context="cycle"):
    return s3.cycle(inputs, context)


def beat(s3, load, context="cycle", **kwargs):
    got = run(s3, make(load=load, **kwargs), context)
    return got


# --------------------------------------------------------------------- kill
def test_redirect_kills_the_beat(s3):
    got = beat(s3, pipe(uop_robIdx_value=30),
               "redirect",
               redirect={"level": 0, "robIdx_flag": 0, "robIdx_value": 5,
                         "robIdx_isFormer": 0})
    assert got["pipeOut_valid"] == 0
    assert got["detail"]["kill"] == 1
    s3.coverage.sample_case("kill.current_redirect")


# ------------------------------------------------------------ head/tail merge
def test_a_tail_cancels_the_present_head(s3):
    got = beat(s3, pipe(unalignHead=1), "cancel", tail_valid=1)
    assert got["detail"]["cancel"] == 1
    assert got["ldout_valid"] == 0, "the cancelled head writes nothing"
    assert got["lq_write_valid"] == 0
    assert got["cancel"] == 1
    # A cancelled head emits the merged (head) beat towards S4.
    assert got["pipeOut_valid"] == 1
    s3.coverage.sample_case("cancel.head_cancelled_by_tail")


def test_no_tail_means_no_cancel(s3):
    got = beat(s3, pipe(unalignHead=1), "no tail", tail_valid=0)
    assert got["detail"]["cancel"] == 0
    assert got["ldout_valid"] == 1
    s3.coverage.sample_case("cancel.no_tail_no_cancel")


def test_exception_head_writes_back_without_waiting_for_the_tail(s3):
    got = beat(s3, pipe(unalignHead=1, uop_exceptionVec_13=1), "exc head",
               concat_valid=1, concat_bits=concat(writebackDependOnTail=1),
               tail_valid=0)
    assert got["detail"]["s3_exception"] == 1
    out = got["pipeOut_bits"]
    assert out["hasException"] == 1
    assert out["headAlwaysWriteback"] == 1
    assert out["writebackDependOnTail"] == 0
    assert got["ldout_valid"] == 1, "the head must not wait for a tail"
    s3.coverage.sample_case("concat.head_always_writeback")


def test_clean_head_defers_the_writeback_to_the_tail(s3):
    got = beat(s3, pipe(unalignHead=1, shouldWriteback=0), "delayed",
               concat_valid=1,
               concat_bits=concat(writebackDependOnTail=1), tail_valid=0)
    assert got["pipeOut_bits"]["headAlwaysWriteback"] == 0
    # ``writebackDependOnTail`` mirrors the *head's* shouldWriteback.
    assert got["pipeOut_bits"]["writebackDependOnTail"] == 0
    assert got["ldout_valid"] == 0, "the tail has not arrived yet"
    # The same head with shouldWriteback high does write back.
    got = beat(s3, pipe(unalignHead=1, shouldWriteback=1), "delayed ok",
               concat_valid=1,
               concat_bits=concat(writebackDependOnTail=1), tail_valid=0)
    assert got["ldout_valid"] == 1
    s3.coverage.sample_case("concat.writeback_depends_on_tail")


def test_tail_exception_vector_replaces_the_head_vector(s3):
    load = pipe(unalignHead=1, uop_exceptionVec_3=0, fullva=0x1000,
                paddr=0x1000, gpaddr=0x1)
    got = beat(s3, load, "tail exc",
               concat_valid=1, tail_valid=1,
               concat_bits=concat(hasException=1, uop_exceptionVec_3=1,
                                  fullva=0x2000, paddr=0x2000, gpaddr=0x2))
    assert got["detail"]["cancel"] == 1
    # Sample actual public outputs, not just a reference-model cancel flag.
    assert int(s3.ldout["exceptionVec_3"].value) == 1
    assert int(s3.lq["uop_exceptionVec_3"].value) == 1
    assert int(s3.exception_info["vaddr"].value) == 0x2000
    s3.coverage.sample_case("concat.tail_exception_replaces_head")


def test_tail_only_beat_uses_the_tail_payload(s3):
    load = pipe(unalignHead=0, paddr=0x1111, vaddr=0x1111, mask=0x0003)
    got = beat(s3, load, "tail only",
               concat_valid=1, tail_valid=0,
               concat_bits=concat(paddr=0x2222, vaddr=0x2222, mask=0x00F0,
                                  headAlwaysWriteback=1, entrance=TAIL_LANE,
                                  cause_6=1, causeOrR=1, mshrId=9, tlbId=3,
                                  tlbFull=1, handledByMSHR=1))
    assert got["lq_write_valid"] == 1
    assert got["lq"]["paddr"] == 0x2222
    assert got["lq"]["vaddr"] == 0x2222
    assert got["lq"]["mask"] == 0x00F0
    assert got["lq"]["rep_info_mshr_id"] == 9
    assert got["lq"]["rep_info_tlb_id"] == 3
    assert got["lq"]["rep_info_tlb_full"] == 1
    assert got["lq"]["handledByMSHR"] == 1
    # With a replayed tail the LQ entry is attributed to the unaligned head.
    assert got["lq"]["rep_info_rep_from_unalign_head"] == 1
    # The tail lane's entrance bit 0 is not an "is replay" code (0x02/0x08 are).
    assert got["lq"]["isLoadReplay"] == 0
    s3.coverage.sample_case("concat.tail_only_uses_tail_payload")
    s3.coverage.sample_case("lq.rep_info_mshr")
    s3.coverage.sample_case("lq.rep_info_tlb_hint")


# ----------------------------------------------------------------- exceptions
def test_any_exception_bit_marks_the_beat(s3):
    for bit in EXC_BITS:
        got = beat(s3, pipe(**{bit: 1}), bit)
        assert got["detail"]["s3_exception"] == 1, bit
        assert got["pipeOut_bits"]["hasException"] == 1, bit
        assert got["pipeOut_bits"]["headAlwaysWriteback"] == 1, bit
    s3.coverage.sample_case("exc.s3_exception_from_any_bit")


def test_trigger_breakpoint_counts_as_an_exception(s3):
    got = beat(s3, pipe(uop_trigger=1), "trigger")
    assert got["detail"]["s3_exception"] == 1
    assert got["ldout"]["trigger"] == 1
    s3.coverage.sample_case("exc.trigger_breakpoint")


# ---------------------------------------------------------------- writeback
def test_scalar_load_returns_through_ldout(s3):
    got = beat(s3, pipe(), "scalar")
    assert got["ldout_valid"] == 1
    assert got["vldout_valid"] == 0
    assert got["ldout"]["robIdx_value"] == 16
    s3.coverage.sample_case("wb.scalar_writeback")


def test_vector_load_returns_through_vldout(s3):
    got = beat(s3, pipe(uop_vecWen=1, accessType_instrType=3), "vector")
    assert got["vldout_valid"] == 1
    assert got["ldout_valid"] == 0
    assert got["vldout"]["robIdx_value"] == 16
    s3.coverage.sample_case("wb.vector_writeback")


def test_no_writeback_when_should_writeback_is_low(s3):
    got = beat(s3, pipe(shouldWriteback=0), "no wb")
    assert got["ldout_valid"] == 0
    assert got["vldout_valid"] == 0
    s3.coverage.sample_case("wb.suppressed_by_mismatch")


# ------------------------------------------------------------------- RF writes
@pytest.mark.parametrize("flag,field,case", [
    ("uop_rfWen", "int_rf_valid", "rfw.int_rf_write_on_wakeup"),
    ("uop_fpWen", "fp_rf_valid", "rfw.fp_rf_write_on_wakeup"),
    ("uop_v0Wen", "v0_rf_valid", "rfw.v0_rf_write_on_wakeup"),
])
def test_scalar_register_write_requires_wakeup(s3, flag, field, case):
    got = beat(s3, pipe(**{flag: 1}), case)
    assert got[field] == 1
    got = beat(s3, pipe(**{flag: 1, "shouldWakeup": 0}), case + " no wake")
    assert got[field] == 0, "no wakeup means no register write"
    s3.coverage.sample_case(case)
    s3.coverage.sample_case("rfw.no_write_without_wakeup")


def test_vector_wakeup_targets_the_vector_register_file(s3):
    got = beat(s3, pipe(uop_vecWen=1), "vec wake")
    assert got["vld_wakeup"] == 1
    assert got["vec_rf_valid"] == 1
    assert got["pdest"] == 7
    s3.coverage.sample_case("rfw.vec_wakeup")


# ------------------------------------------------------------------- LQ write
def test_normal_beat_writes_the_load_queue(s3):
    got = beat(s3, pipe(uncacheReplay=1, ncReplay=1, pmp_mmio=0,
                        accessType_instrType=3, size=3, replayQueueIdx=0x2A,
                        entrance=REPLAY_HI), "lq")
    entry = got["lq"]
    assert entry["nc"] == 1
    assert entry["memBackTypeMM"] == 1
    assert entry["isvec"] == 1
    assert entry["alignedType"] == 3
    assert entry["schedIndex"] == 0x2A
    assert entry["updateAddrValid"] == 1
    assert entry["rep_info_last_beat"] == (0x1234_5000 >> 5) & 1
    assert entry["rep_info_need_rep"] == 0
    assert entry["isLoadReplay"] == 1
    s3.coverage.sample_case("lq.write_valid_normal")
    s3.coverage.sample_case("lq.nc_from_replay")
    s3.coverage.sample_case("lq.is_vec_and_aligned_type")
    s3.coverage.sample_case("lq.is_load_replay_entrance")
    s3.coverage.sample_case("lq.rep_info_last_beat")


def test_mem_back_type_follows_pmp_mmio(s3):
    got = beat(s3, pipe(pmp_mmio=1), "pmp mmio")
    assert got["lq"]["memBackTypeMM"] == 0
    s3.coverage.sample_case("lq.mem_back_type")


def test_accepted_fast_replay_suppresses_the_lq_write(s3):
    got = beat(s3, pipe(shouldFastReplay=1), "fast accepted", fast_ready=1)
    assert got["fast_replay_valid"] == 1
    assert got["lq_write_valid"] == 0
    got = beat(s3, pipe(shouldFastReplay=1), "fast backpressured", fast_ready=0)
    assert got["fast_replay_valid"] == 1
    assert got["lq_write_valid"] == 1, "a backpressured replay still writes the LQ"
    s3.coverage.sample_case("lq.suppressed_by_accepted_fast_replay")
    s3.coverage.sample_case("replay.fast_replay_valid")


def test_rr_bank_conflict_grant_overrides_the_replay_hold(s3):
    # A bank-conflict fast replay is only accepted once the RR arbiter grants;
    # without the grant the LQ write still happens.
    got = beat(s3, pipe(shouldFastReplay=1, rrBankConflictFastReplay=1),
               "rr no grant", fast_ready=1)
    assert got["fast_replay_valid"] == 0
    assert got["lq_write_valid"] == 1
    got = beat(s3, pipe(shouldFastReplay=1, rrBankConflictFastReplay=1,
                        rrBankConflictFastReplayGrant=1), "rr grant", fast_ready=1)
    assert got["fast_replay_valid"] == 1
    assert got["lq_write_valid"] == 0
    s3.coverage.sample_case("replay.rr_grant_required")


def test_replay_cause_is_encoded_one_hot(s3):
    for cause, bit in CAUSE_OH.items():
        got = beat(s3, pipe(**{f"cause_{cause}": 1, "causeOrR": 1}),
                   f"cause {cause}")
        assert got["lq"]["rep_info_need_rep"] == 1, cause
        assert got["lq"][f"rep_info_cause_{bit.bit_length() - 1}"] == 1, cause
        assert sum(got["lq"][f"rep_info_cause_{i}"] for i in range(13)) == 1
    s3.coverage.sample_case("lq.rep_info_cause_one_hot")


def test_special_mode_eligible_requires_the_tail_replay(s3):
    got = beat(s3, pipe(cause_5=1), "sm head",
               concat_valid=1, concat_bits=concat(cause_5=1, causeOrR=1))
    assert got["lq"]["specialModeEligible"] == 1
    assert got["lq"]["rep_info_rep_from_unalign_head"] == 1
    got = beat(s3, pipe(cause_5=1), "sm no concat")
    assert got["lq"]["specialModeEligible"] == 0
    s3.coverage.sample_case("lq.special_mode_eligible")
    s3.coverage.sample_case("lq.rep_from_unalign_head")


# ------------------------------------------------------------ replay / revoke
def test_revoke_reports_the_current_and_previous_cycle(s3):
    got = beat(s3, pipe(uop_exceptionVec_13=1), "revoke")
    assert got["revoke_last"] == 1
    assert got["revoke_last_last"] == 0
    # A clean tail in front of a revoking head yields both flags.
    got = beat(s3, pipe(causeOrR=1), "revoke pair",
               concat_valid=1,
               concat_bits=concat(hasException=0, causeOrR=0))
    assert got["revoke_last"] == 1, "the head's revoke propagates immediately"
    assert got["revoke_last_last"] == 1
    s3.coverage.sample_case("replay.revoke_last_cycle")
    s3.coverage.sample_case("replay.revoke_last_last_cycle")


# ------------------------------------------------------------------ rollback
def test_rar_violation_rolls_back(s3):
    got = beat(s3, pipe(accessType_instrType=1), "rar",
               rar_valid=1, rar_nuke=1, ldld=1)
    assert got["detail"]["s3_rar_violation"] == 1
    assert got["rollback_valid"] == 1
    assert got["rollback"]["level"] == 0
    s3.coverage.sample_case("rollback.rar_violation")


def test_rar_violation_needs_the_ldld_check_enable(s3):
    got = beat(s3, pipe(), "rar disabled", rar_valid=1, rar_nuke=1, ldld=0)
    assert got["rollback_valid"] == 0


def test_match_invalid_rolls_back_at_level(s3):
    got = beat(s3, pipe(matchInvalid=1), "match invalid")
    assert got["rollback_valid"] == 1
    assert got["rollback"]["level"] == 1
    assert got["pipeOut_bits"]["matchInvalid"] == 1
    assert got["pipeOut_bits"]["headAlwaysWriteback"] == 1
    s3.coverage.sample_case("rollback.match_invalid")
    s3.coverage.sample_case("rollback.level_follows_match_invalid")


# --------------------------------------------------------------- exceptionInfo
def test_exception_info_only_for_scalar_non_mmio_writebacks(s3):
    got = beat(s3, pipe(uop_exceptionVec_13=1, fullva=0x8000_5000), "excinfo")
    assert got["exception_info_valid"] == 1
    assert got["excinfo"]["vaddr"] == 0x8000_5000
    assert got["excinfo"]["gpaddr"] == 0
    assert got["excinfo"]["exceptionVec_13"] == 1
    assert got["excinfo"]["robIdx_value"] == 16
    # An MMIO replay does not raise an exception record here.
    got = beat(s3, pipe(uop_exceptionVec_13=1, uncacheReplay=1, ncReplay=0),
               "mmio")
    assert got["exception_info_valid"] == 0
    # A vector beat never produces the scalar exception record.
    got = beat(s3, pipe(uop_exceptionVec_13=1, uop_vecWen=1), "vector")
    assert got["exception_info_valid"] == 0
    s3.coverage.sample_case("excinfo.scalar_only_and_not_mmio")
    s3.coverage.sample_case("excinfo.payload_fields")


# --------------------------------------------------------------------- cancel
def test_cancel_output_flags_a_misaligned_beat_without_wakeup(s3):
    got = beat(s3, pipe(accessType_instrType=1, shouldWakeup=0), "cancel out")
    assert got["cancel_out"] == 1
    s3.coverage.sample_case("cancel.output_when_misaligned_and_no_wakeup")


# ------------------------------------------------------------- output register
def test_payload_register_holds_when_the_stage_is_empty(s3):
    # pipeOut is the head/tail *merge* beat: it is only valid when a tail
    # cancels the present head, but the payload registers still capture every
    # valid input beat.
    got = beat(s3, pipe(uop_pdest=0x31, unalignHead=1), "fill", tail_valid=1)
    assert got["pipeOut_valid"] == 1
    assert got["pipeOut_bits"]["entrance"] == SCALAR
    got = run(s3, blank_inputs(), "empty")
    assert got["pipeOut_valid"] == 0
    s3.coverage.sample_case("reg.payload_holds")


def test_status_bits_return_to_zero_on_the_next_beat(s3):
    """The revoke / RAR-violation / match-invalid wires are live per beat; drive
    a set beat followed by a clean beat in the same instance so both toggle
    directions are seen. Cause 11 (nuke) is the highest one-hot bit."""
    run(s3, make(load=pipe(cause_11=1, causeOrR=1)), "cause11 set")
    got = run(s3, make(load=pipe()), "cause11 clear")
    assert got["lq"]["rep_info_cause_11"] == 0
    # An exception masks both the RAR violation and the match-invalid flags, so
    # each is exercised on its own beat.
    run(s3, make(load=pipe(), rar_valid=1, rar_nuke=1, ldld=1), "rar set")
    got = run(s3, make(load=pipe()), "rar clear")
    assert got["detail"]["s3_rar_violation"] == 0
    run(s3, make(load=pipe(matchInvalid=1)), "mi set")
    got = run(s3, make(load=pipe()), "mi clear")
    assert got["detail"]["match_invalid"] == 0
    run(s3, make(load=pipe(uop_exceptionVec_13=1)), "exc set")
    got = run(s3, make(load=pipe()), "exc clear")
    assert got["detail"]["s3_exception"] == 0
    assert got["revoke_last"] == 0
    s3.coverage.sample_case("lq.rep_info_cause_one_hot")


# ---------------------------------------------------------------------- random
def test_seeded_random_traffic(s3):
    rng = random.Random(20261025)
    for cycle in range(300):
        run(s3, random_inputs(rng), f"random {cycle}")


def test_case_inventory_is_exact():
    assert len(CASES) == len(set(CASES))
    assert len(CASES) == 40
