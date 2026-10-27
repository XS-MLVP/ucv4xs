"""LoadUnitDataPath UT: byte merge, rotate and extend."""
from __future__ import annotations

import random

import pytest

from lsuverify.load_datapath.coverage import CASES, LoadDataPathCoverage
from lsuverify.load_datapath.env import (
    FORWARD_SOURCES,
    LoadDataPathEnv,
    blank_forward,
    extend_value,
    random_forward,
    shift_right_bytes,
)

FU_LBU, FU_LHU, FU_LWU, FU_LD = 0x10, 0x12, 0x14, 0x06
FU_LB, FU_LH, FU_LW = 0x00, 0x02, 0x04
FU_LH_FP, FU_LW_FP = 0x02, 0x04


@pytest.fixture
def ldp(dut_factory):
    dut = dut_factory("load_datapath")
    env = LoadDataPathEnv(dut, LoadDataPathCoverage())
    env.reset()
    return env


def meta(bank=0, fu=FU_LD, fp=0, nc=0, mmio=0, head=0):
    return {"bankOffset": bank, "fuOpType": fu, "fpWen": fp, "isNCReplay": nc,
            "isMMIOReplay": mmio, "isUnalignHead": head}


def run(ldp, s1_valid=0, s1_meta=None, forward=None, tld_valid=0, tld_data=None,
        bypass=0, dcache=0, context="cycle"):
    return ldp.cycle(s1_valid, s1_meta or meta(), forward or blank_forward(),
                     tld_valid, tld_data or [0] * 16, bypass, dcache, context)


def prime(ldp, s1_meta, forward=None, tld_valid=0, tld_data=None, bypass=0, dcache=0):
    """Load S1 and let the data reach S3; returns the S3 observation."""
    run(ldp, 1, s1_meta, forward, tld_valid, tld_data, bypass, dcache, "prime s1")
    return run(ldp, 0, s1_meta, forward, tld_valid, tld_data, bypass, dcache,
               "prime s2")


# ------------------------------------------------------------------- pipeline
def test_metadata_register_and_clear(ldp):
    run(ldp, 1, meta(bank=3, fu=FU_LD), context="load")
    assert ldp.model.state.s2_valid == 1
    assert ldp.model.state.s2_meta["bankOffset"] == 3
    run(ldp, 0, context="clear")
    assert ldp.model.state.s2_valid == 0
    assert ldp.model.state.s2_meta["bankOffset"] == 3, "payload must hold"
    ldp.coverage.sample_case("meta.register_and_clear")
    ldp.coverage.sample_case("meta.hold_when_empty")


def test_valid_chain_latency(ldp):
    """s2Valid <= s1Meta.valid and s3Valid <= s2Valid, so one S1 beat produces an
    S3 beat one cycle later and nothing after that."""
    assert run(ldp, 1, meta(), context="c0")["s3_valid"] == 0
    assert run(ldp, 0, context="c1")["s3_valid"] == 1
    assert run(ldp, 0, context="c2")["s3_valid"] == 0
    ldp.coverage.sample_case("valid.chain_latency")


# --------------------------------------------------------------------- merge
def test_sq_forward_wins_over_every_other_source(ldp):
    forward = random_forward(random.Random(1), density=1.0)
    dcache = 0x1111_2222_3333_4444_5555_6666_7777_8888
    got = prime(ldp, meta(fu=FU_LD), forward, tld_valid=1,
                tld_data=[0xAA] * 16, bypass=0xBB, dcache=dcache)
    data = got["shift_data"]
    for index in range(16):
        assert (data >> (8 * index)) & 0xFF == forward["sq"]["data"][index], index
    ldp.coverage.sample_case("merge.sq_priority_over_all")


def test_uncache_forward_needs_nc_replay(ldp):
    forward = blank_forward()
    forward["uncache"] = {"mask": [1] * 16, "data": [0x5A] * 16}
    dcache = 0xC0DE
    got = prime(ldp, meta(fu=FU_LD, nc=1), forward, dcache=dcache)
    assert all((got["shift_data"] >> (8 * i)) & 0xFF == 0x5A for i in range(16))
    got = prime(ldp, meta(fu=FU_LD, nc=0), forward, dcache=dcache)
    assert all((got["shift_data"] >> (8 * i)) & 0xFF
               == (dcache >> (8 * i)) & 0xFF for i in range(16))
    ldp.coverage.sample_case("merge.uncache_requires_nc_replay")


def test_sbuffer_wins_over_mshr_and_tld(ldp):
    forward = blank_forward()
    forward["sbuffer"] = {"mask": [1] * 16, "data": [0x33] * 16}
    forward["mshr"] = {"mask": [1] * 16, "data": [0x44] * 16}
    got = prime(ldp, meta(fu=FU_LD), forward, tld_valid=1, tld_data=[0x55] * 16)
    assert all((got["shift_data"] >> (8 * i)) & 0xFF == 0x33 for i in range(16))
    ldp.coverage.sample_case("merge.sbuffer_priority_over_mshr")


def test_mshr_wins_over_tld(ldp):
    forward = blank_forward()
    forward["mshr"] = {"mask": [1] * 16, "data": [0x44] * 16}
    got = prime(ldp, meta(fu=FU_LD), forward, tld_valid=1, tld_data=[0x55] * 16)
    assert all((got["shift_data"] >> (8 * i)) & 0xFF == 0x44 for i in range(16))
    ldp.coverage.sample_case("merge.mshr_priority_over_tld")


def test_tld_wins_over_raw_data(ldp):
    got = prime(ldp, meta(fu=FU_LD), None, tld_valid=1, tld_data=[0x77] * 16,
                dcache=0x1234)
    assert all((got["shift_data"] >> (8 * i)) & 0xFF == 0x77 for i in range(16))
    ldp.coverage.sample_case("merge.tld_priority_over_raw")


def test_raw_data_comes_from_dcache_or_uncache_bypass(ldp):
    payload = 0x0123_4567_89AB_CDEF_FEDC_BA98_7654_3210
    got = prime(ldp, meta(fu=FU_LD), None, dcache=payload)
    assert got["shift_data"] == payload
    ldp.coverage.sample_case("merge.raw_from_dcache")
    got = prime(ldp, meta(fu=FU_LD, nc=1), None, bypass=payload, dcache=0)
    assert got["shift_data"] == payload
    ldp.coverage.sample_case("merge.raw_from_uncache_bypass_on_nc")
    got = prime(ldp, meta(fu=FU_LD, mmio=1), None, bypass=payload, dcache=0)
    assert got["shift_data"] == payload
    ldp.coverage.sample_case("merge.raw_from_uncache_bypass_on_mmio")


# -------------------------------------------------------------------- rotate
def test_each_bank_offset_rotates_the_data(ldp):
    payload = 0x0011_2233_4455_6677_8899_AABB_CCDD_EEFF
    for offset in range(16):
        got = prime(ldp, meta(bank=offset, fu=FU_LD), None, dcache=payload)
        assert got["shift_data"] == shift_right_bytes(payload, offset), offset
    ldp.coverage.sample_case("rotate.each_bank_offset")


def test_offset_zero_is_the_identity(ldp):
    payload = 0xDEAD_BEEF_0123_4567_89AB_CDEF_0011_2233
    got = prime(ldp, meta(bank=0, fu=FU_LD), None, dcache=payload)
    assert got["shift_data"] == payload
    ldp.coverage.sample_case("rotate.offset_zero_identity")


# -------------------------------------------------------------------- extend
@pytest.mark.parametrize("fu,width,case", [
    (FU_LBU, 1, "extend.unsigned_byte_half_word_word"),
    (FU_LHU, 2, "extend.unsigned_byte_half_word_word"),
    (FU_LWU, 4, "extend.unsigned_byte_half_word_word"),
    (FU_LD, 8, "extend.double_word"),
])
def test_unsigned_extensions(ldp, fu, width, case):
    payload = 0x8180_0180_0180_0180
    got = prime(ldp, meta(fu=fu), None, dcache=payload)
    mask = (1 << (8 * width)) - 1
    assert got["shift_and_ext"] == payload & mask, fu
    ldp.coverage.sample_case(case)


@pytest.mark.parametrize("fu,width,case", [
    (FU_LB, 1, "extend.signed_byte_half_word_word"),
    (FU_LH, 2, "extend.signed_byte_half_word_word"),
    (FU_LW, 4, "extend.signed_byte_half_word_word"),
])
def test_signed_extensions(ldp, fu, width, case):
    payload = 0x8180_0180_0180_0180
    got = prime(ldp, meta(fu=fu), None, dcache=payload)
    assert got["shift_and_ext"] == extend_value(payload, fu, 0), fu
    selected = payload & ((1 << (8 * width)) - 1)
    if selected >> (8 * width - 1):
        assert got["shift_and_ext"] >> (8 * width) == (1 << (64 - 8 * width)) - 1, fu
    ldp.coverage.sample_case(case)


def test_fp_loads_are_nan_boxed(ldp):
    payload = 0xFFFF_0000_0000_8001
    got = prime(ldp, meta(fu=FU_LH_FP, fp=1), None, dcache=payload)
    assert got["shift_and_ext"] == (0xFFFF_FFFF_FFFF << 16) | 0x8001
    ldp.coverage.sample_case("extend.fp16_nan_box")
    got = prime(ldp, meta(fu=FU_LW_FP, fp=1), None, dcache=payload)
    assert got["shift_and_ext"] == (0xFFFF_FFFF << 32) | 0x0000_8001
    ldp.coverage.sample_case("extend.fp32_nan_box")


def test_unknown_optype_produces_zero(ldp):
    got = prime(ldp, meta(fu=0xABC), None, dcache=0xFFFF_FFFF_FFFF_FFFF)
    assert got["shift_and_ext"] == 0
    ldp.coverage.sample_case("extend.unknown_optype_is_zero")


# ---------------------------------------------------------------------- tail
def test_tail_merges_the_previous_head_with_the_shifted_tail(ldp):
    head = 0xA1B2_C300_0000_0000_0000_00AA_BBCC_DDEE
    tail = 0x1111_2222_3333_4444_5555_6666_7777_8888
    run(ldp, 1, meta(bank=13, fu=FU_LD, head=1), None, dcache=head, context="head s1")
    # Tail S1 and head S2 coincide; a bubble would miss the tail-merge path.
    run(ldp, 1, meta(bank=0, fu=FU_LD), None, dcache=head, context="head s2 / tail s1")
    got = run(ldp, 0, None, None, dcache=tail, context="tail s2")
    assert got["s3_valid"] == 1
    expected = ((head >> 104) | (tail << 24)) & ((1 << 128) - 1)
    assert int(ldp.out_shift.value) == expected
    assert int(ldp.out_ext.value) == expected & ((1 << 64) - 1)
    ldp.coverage.sample_case("tail.head_data_is_merged_with_shifted_tail")


def test_tail_with_zero_head_offset_uses_head_only(ldp):
    head = 0xAAAA_BBBB_CCCC_DDDD_EEEE_FFFF_0000_1111
    tail = 0x2222_3333_4444_5555_6666_7777_8888_9999
    run(ldp, 1, meta(bank=0, fu=FU_LD, head=1), None, dcache=head, context="h1")
    run(ldp, 1, meta(bank=0, fu=FU_LD), None, dcache=head, context="h2/t1")
    got = run(ldp, 0, None, None, dcache=tail, context="t2")
    assert got["s3_valid"] == 1
    assert int(ldp.out_shift.value) == head
    assert int(ldp.out_ext.value) == head & ((1 << 64) - 1)
    ldp.coverage.sample_case("tail.offset_zero_uses_head_only")


# -------------------------------------------------------------------- random
def test_seeded_random_traffic(ldp):
    rng = random.Random(20261025)
    for cycle in range(300):
        s1_valid = 1 if rng.random() < 0.7 else 0
        m = meta(bank=rng.randrange(16),
                 fu=rng.choice([FU_LBU, FU_LHU, FU_LWU, FU_LD, FU_LB, FU_LH, FU_LW,
                                FU_LH_FP, FU_LW_FP, 0xABC]),
                 fp=rng.randrange(2), nc=rng.randrange(2), mmio=rng.randrange(2),
                 head=1 if rng.random() < 0.25 else 0)
        run(ldp, s1_valid, m, random_forward(rng, 0.15),
            tld_valid=1 if rng.random() < 0.2 else 0,
            tld_data=[rng.randrange(256) for _ in range(16)],
            bypass=rng.getrandbits(128), dcache=rng.getrandbits(128),
            context=f"random {cycle}")


def test_case_inventory_is_exact():
    assert len(CASES) == len(set(CASES))
    assert len(CASES) == 21


def test_fuoptype_full_width_and_every_encoding_family(ldp):
    """Walk all 12 fuOpType bits and cover the HLV/HLVX encodings (0x40.., 0x50..,
    0x70..), whose decodes share the same 9 one-hot buckets."""
    payload = 0x8180_0180_0180_0180
    for bit in range(12):
        got = prime(ldp, meta(fu=1 << bit), None, dcache=payload)
        assert got["s3_valid"] == 1
    for fu in (0x40, 0x42, 0x44, 0x46, 0x50, 0x52, 0x54, 0x72, 0x74):
        got = prime(ldp, meta(fu=fu), None, dcache=payload)
        assert got["s3_valid"] == 1
        assert got["shift_and_ext"] == extend_value(payload, fu, 0), hex(fu)
    # Clear back to 0 so the 1->0 toggle directions are seen too.
    prime(ldp, meta(fu=0), None, dcache=0)
