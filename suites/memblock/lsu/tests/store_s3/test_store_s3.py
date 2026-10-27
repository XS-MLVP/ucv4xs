"""StoreUnitS3 UT: head-only pipeOut plus the writeback delay pipe."""
from __future__ import annotations

import random

import pytest

from lsuverify.common.robptr import LEVEL_FLUSH, LEVEL_FLUSH_AFTER
from lsuverify.store_s3.coverage import S3_CASES, StoreS3Coverage
from lsuverify.store_s3.env import (
    CONCAT_FIELDS,
    PIPE_IN_FIELDS,
    StoreS3Env,
    blank,
    blank_redirect,
    random_concat,
    random_pipe_in,
)


@pytest.fixture
def s3(dut_factory):
    dut = dut_factory("store_s3")
    env = StoreS3Env(dut, StoreS3Coverage())
    env.reset()
    return env


def run(s3, in_valid=0, in_bits=None, concat_valid=0, concat=None, redirect=None,
        context="cycle"):
    return s3.cycle(in_valid, in_bits or blank(PIPE_IN_FIELDS), concat_valid,
                    concat or blank(CONCAT_FIELDS), redirect or blank_redirect(),
                    context)


def beat(instr_type=1, rob=10, unalign_head=0, is_cbo=0, mmio=0, nc=0,
         mem_back=1, need_replay=0, has_exception=0, exc7=0, exc15=0, exc23=0,
         fullva=0x5000, gpaddr=0xAA, trigger=0xF, va_ext=0, hyper=0, non_leaf=0,
         exc6=0, exc19=0, exc3=0, **overrides):
    values = dict(
        accessType_instrType=instr_type, accessType_isCbo=is_cbo,
        uop_exceptionVec_23=exc23, uop_exceptionVec_19=exc19,
        uop_exceptionVec_15=exc15, uop_exceptionVec_7=exc7,
        uop_exceptionVec_6=exc6, uop_exceptionVec_3=exc3, uop_trigger=trigger,
        uop_robIdx_flag=0, uop_robIdx_value=rob, uop_robIdx_isFormer=1,
        fullva=fullva, unalignHead=unalign_head, tlbException_vaNeedExt=va_ext,
        tlbException_isHyper=hyper, isForVSnonLeafPTE=non_leaf, gpaddr=gpaddr,
        hasException=has_exception, needRSReplay=need_replay, nc=nc, mmio=mmio,
        memBackTypeMM=mem_back,
    )
    values.update(overrides)
    return values


# ------------------------------------------------------------------ pipeOut
def test_pipe_out_only_carries_head_beats(s3):
    got = run(s3, 1, beat(unalign_head=1), context="head")
    assert got["pipe_out_valid"] == 1
    s3.coverage.sample_case("pipeout.only_head_beats")
    s3.coverage.sample_case("pipeout.head_registers_one_cycle")
    got = run(s3, 0, context="consumed")
    assert got["pipe_out_valid"] == 0
    got = run(s3, 1, beat(unalign_head=0), context="tail")
    assert got["pipe_out_valid"] == 0
    s3.coverage.sample_case("pipeout.tail_suppressed")


def test_pipe_out_redirect_kill_and_reset(s3):
    got = run(s3, 1, beat(rob=10, unalign_head=1),
              redirect=dict(valid=1, level=LEVEL_FLUSH, flag=0, value=10, former=1),
              context="kill")
    assert got["pipe_out_valid"] == 0
    s3.coverage.sample_case("pipeout.killed_by_redirect")
    # Idle keeps the valid low after reset.
    assert int(s3.out_valid.value) == 0
    s3.coverage.sample_case("pipeout.reset_clears_valid")


def test_pipe_out_field_fidelity(s3):
    rng = random.Random(51)
    for cycle in range(30):
        values = random_pipe_in(rng, unalignHead=1)
        got = run(s3, 1, values, context=f"field {cycle}")
        if got["pipe_out_valid"]:
            assert got["pipe_out_bits"]["fullva"] == values["fullva"] & ((1 << 64) - 1)
    s3.coverage.sample_case("pipeout.field_fidelity")


# ------------------------------------------------------------ writeback pipe
def test_normal_store_is_written_back(s3):
    """out.ready is tied high, so the writeback is visible after the entry edge."""
    got = run(s3, 1, beat(), context="enter")
    assert got["stout_valid"] == 1
    assert got["stout_bits"]["robIdx_value"] == 10
    assert run(s3, 0, context="next")["stout_valid"] == 0
    s3.coverage.sample_case("delay.normal_store_written_back")
    s3.coverage.sample_case("delay.one_cycle_latency")


@pytest.mark.parametrize("case,has_exc,want", [
    ("mmio_no_exc", 0, 0), ("mmio_exc", 1, 1),
    ("cbo_no_exc", 0, 0),
])
def test_mmio_and_cbo_need_an_exception_to_be_written_back(s3, case, has_exc, want):
    kw = {"mmio": 1} if case.startswith("mmio") else {"is_cbo": 1}
    got = run(s3, 1, beat(has_exception=has_exc, **kw), context="enter")
    assert got["stout_valid"] == want
    s3.coverage.sample_case({"mmio_no_exc": "delay.mmio_suppressed_without_exception",
                             "mmio_exc": "delay.mmio_allowed_with_exception",
                             "cbo_no_exc": "delay.cbo_suppressed_without_exception"}[case])


def test_prefetch_head_and_replay_suppress_the_writeback(s3):
    assert run(s3, 1, beat(instr_type=4), context="prefetch")["stout_valid"] == 0
    s3.coverage.sample_case("delay.prefetch_suppressed")
    assert run(s3, 1, beat(unalign_head=1), context="head")["stout_valid"] == 0
    s3.coverage.sample_case("delay.head_suppressed")
    assert run(s3, 1, beat(need_replay=1), context="replay")["stout_valid"] == 0
    s3.coverage.sample_case("delay.replay_suppressed")


def test_writeback_is_dropped_by_a_redirect_in_the_entry_cycle(s3):
    got = run(s3, 1, beat(rob=20),
              redirect=dict(valid=1, level=LEVEL_FLUSH_AFTER, flag=0, value=19,
                            former=1), context="kill at entry")
    assert got["stout_valid"] == 0
    s3.coverage.sample_case("delay.killed_by_redirect")


def test_vector_store_produces_no_rob_writeback(s3):
    got = run(s3, 1, beat(instr_type=2), context="vector")
    assert got["stout_valid"] == 0
    s3.coverage.sample_case("delay.vector_produces_no_writeback")


# ---------------------------------------------------------------- mixed payload
def test_exception_payload_comes_from_the_concat_path(s3):
    concat = random_concat(random.Random(61))
    concat["hasException"] = 1
    concat["uop_exceptionVec_7"] = 1
    normal = beat(exc7=0, fullva=0x1111, trigger=0x1)
    got = run(s3, 1, normal, 1, concat, context="mix")
    assert got["head_has_exception"] == 1
    assert got["stout_valid"] == 1
    assert got["stout_bits"]["exceptionVec_7"] == concat["uop_exceptionVec_7"]
    assert got["stout_bits"]["trigger"] == concat["uop_trigger"]
    assert got["exception_bits"]["vaddr"] == concat["fullva"]
    s3.coverage.sample_case("mix.exception_payload_from_concat_when_head_has_exception")


def test_clean_head_uses_the_normal_payload(s3):
    concat = random_concat(random.Random(62))
    concat["hasException"] = 0
    normal = beat(exc7=1, fullva=0x2222, trigger=0x2)
    got = run(s3, 1, normal, 1, concat, context="clean")
    assert got["head_has_exception"] == 0
    assert got["stout_bits"]["exceptionVec_7"] == 1
    assert got["stout_bits"]["trigger"] == 0x2
    assert got["exception_bits"]["vaddr"] == 0x2222
    s3.coverage.sample_case("mix.normal_payload_from_pipe_when_head_is_clean")


def test_control_fields_always_come_from_the_pipe(s3):
    concat = random_concat(random.Random(63), hasException=1)
    normal = beat(nc=1, mmio=0, mem_back=0)
    got = run(s3, 1, normal, 1, concat, context="control")
    assert got["stout_bits"]["debugInfo_isNCIO"] == 1
    assert got["stout_bits"]["debugInfo_isMMIO"] == 0
    s3.coverage.sample_case("mix.control_fields_stay_from_pipe")


# ------------------------------------------------------------------ sidebands
def test_debug_info_bits(s3):
    got = run(s3, 1, beat(mmio=1, has_exception=1), context="mmio")
    assert got["stout_bits"]["debugInfo_isMMIO"] == 1
    s3.coverage.sample_case("stout.debug_is_mmio")
    got = run(s3, 1, beat(nc=1, mem_back=0), context="nc io")
    assert got["stout_bits"]["debugInfo_isNCIO"] == 1
    s3.coverage.sample_case("stout.debug_is_ncio")
    got = run(s3, 1, beat(nc=1, mem_back=1), context="nc normal")
    assert got["stout_bits"]["debugInfo_isNCIO"] == 0
    s3.coverage.sample_case("stout.debug_is_ncio_requires_not_mem_back_mm")


def test_exception_info_sideband(s3):
    big_gpaddr = (1 << 64) - 1
    got = run(s3, 1, beat(fullva=0xFEED_FACE_1234_5678, gpaddr=big_gpaddr, va_ext=1,
                          hyper=1, non_leaf=1, exc15=1), context="exc info")
    assert got["exception_valid"] == 1
    assert got["stout_valid"] == 1
    assert got["exception_bits"]["gpaddr"] == big_gpaddr & ((1 << 50) - 1)
    assert got["exception_bits"]["vaddr"] == 0xFEED_FACE_1234_5678
    assert got["exception_bits"]["vaNeedExt"] == 1
    assert got["exception_bits"]["isHyper"] == 1
    assert got["exception_bits"]["isForVSnonLeafPTE"] == 1
    s3.coverage.sample_case("exc.gpaddr_truncated_to_50_bits")
    s3.coverage.sample_case("exc.vaddr_is_fullva")
    s3.coverage.sample_case("exc.sideband_fields")
    s3.coverage.sample_case("exc.valid_matches_stout")


def test_seeded_random_stream_matches_the_model(s3):
    rng = random.Random(20261025)
    for cycle in range(400):
        in_valid = 1 if rng.random() < 0.8 else 0
        values = random_pipe_in(rng, accessType_instrType=rng.choice([1, 1, 2, 4]))
        concat_valid = 1 if rng.random() < 0.3 else 0
        concat = random_concat(rng)
        redir = blank_redirect()
        if rng.random() < 0.25:
            redir = dict(valid=1, level=rng.randrange(2), flag=rng.randrange(2),
                         value=rng.randrange(160), former=rng.randrange(2))
        run(s3, in_valid, values, concat_valid, concat, redir,
            context=f"random {cycle}")


def test_case_inventory_is_exact():
    assert len(S3_CASES) == len(set(S3_CASES))
    assert len(S3_CASES) == 26
