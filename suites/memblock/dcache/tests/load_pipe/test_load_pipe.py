"""LoadPipe UT: pipeline timing, hit/miss classification and miss request fields."""
from __future__ import annotations

import random

import pytest

from dcacheverify.load_pipe.coverage import LoadPipeCoverage
from dcacheverify.load_pipe.env import LoadPipeEnv


@pytest.fixture
def lp(dut_factory):
    dut = dut_factory("load_pipe")
    env = LoadPipeEnv(dut, LoadPipeCoverage())
    env.reset()
    return env


# LP-FP-001, LP-FP-003
def test_hit_all_ways_and_data_concat(lp):
    for way in range(4):
        banks = [0x1000 + way * 0x100 + bank for bank in range(8)]
        result = lp.transaction(vaddr=0x1000, paddr=0x8000, tag_way=way,
                                banks=banks, context=f"hit way {way}")
        assert result["s0"]["req_ready"] == 1
        assert result["s0"]["tag_valid"] == 1
        assert result["s2"]["miss"] == 0
        assert result["s0"]["bdata_way"] == (1 << way)


# LP-FP-002, LP-FP-007
def test_mask_shapes_and_load128(lp):
    for mask in (0x1, 0x18, 0x00FF, 0xFFFF):
        lp.transaction(vaddr=0x1080, paddr=0x9000, mask=mask,
                       context=f"mask {mask:#x}")
    normal = lp.transaction(vaddr=0x1080, paddr=0x9000, mask=0x00FF,
                            context="normal")["s0"]["bdata_bank"]
    wide = lp.transaction(vaddr=0x1080, paddr=0x9000, mask=0x00FF,
                          load128=True, context="load128")["s0"]["bdata_bank"]
    assert wide != normal, (wide, normal)


# LP-FP-004
def test_miss_request_fields_and_suppression(lp):
    result = lp.transaction(vaddr=0x2400, paddr=0xA000, tag_match=False,
                            context="plain miss")
    assert result["s2"]["miss"] == 1
    assert result["s2"]["handled"] == 1
    # mshr full only blocks speculative reservation; the miss is still sent.
    result = lp.transaction(vaddr=0x2400, paddr=0xA000, tag_match=False,
                            mshr_full=True, context="mshr full")
    assert result["s2"]["miss"] == 1
    # writeback queue block keeps the request but suppresses handled.
    result = lp.transaction(vaddr=0x2400, paddr=0xA000, tag_match=False,
                            wbq_block=True, context="wbq block")
    assert result["s2"]["miss"] == 1 and result["s2"]["handled"] == 0
    result = lp.transaction(vaddr=0x2400, paddr=0xA000, tag_match=False,
                            miss_handled=False, context="not handled")
    assert result["s2"]["handled"] == 0
    assert result["s2"]["mshr_id"] == 0


# LP-FP-008
def test_speculative_miss_confirmation(lp):
    result = lp.transaction(vaddr=0x2800, paddr=0xB000, tag_match=False,
                            specmiss=True, spec_grant=False,
                            context="unconfirmed spec")
    assert result["s2"]["miss"] == 1
    result = lp.transaction(vaddr=0x2800, paddr=0xB000, tag_match=False,
                            specmiss=True, spec_grant=True,
                            context="confirmed spec")
    assert result["s2"]["miss_valid"] == 1
    assert result["s2"]["miss_isSpec"] == 1


# LP-FP-006
def test_bank_conflict_outputs(lp):
    result = lp.transaction(vaddr=0x3000, paddr=0xC000, bank_conflict=True,
                            context="bank conflict")
    assert result["s2"]["bank_conflict"] == 1
    result = lp.transaction(vaddr=0x3000, paddr=0xC000, rr_conflict=True,
                            context="rr conflict")
    assert result["s2"]["rr_conflict"] == 1
    lp.coverage.sample_rr_conflict()


# LP-FP-001..008
def test_random_hits_and_misses(lp):
    rng = random.Random(0x1DAD_2026)
    for step in range(60):
        hit = rng.random() < 0.6
        way = rng.randrange(4)
        vaddr = rng.getrandbits(50)
        paddr = rng.getrandbits(48)
        mask = rng.choice((1, 3, 0x18, 0xFF, 0xF0F0, 0xFFFF))
        cmd = rng.choice((0, 1, 2, 3))
        banks = [rng.randrange(1 << 16) for _ in range(8)]
        lp.transaction(vaddr=vaddr, paddr=paddr, tag_match=hit, tag_way=way,
                       mask=mask, cmd=cmd, banks=banks,
                       mshr_full=rng.random() < 0.1,
                       miss_handled=rng.random() < 0.8,
                       bank_conflict=rng.random() < 0.1,
                       context=f"random {step}")


# LP-FP-003, LP-FP-004
def test_outcome_way_matrix(lp):
    banks = [0x10 + bank for bank in range(8)]
    for way in range(4):
        # Hit on every way.
        lp.transaction(vaddr=0x4000 + way * 0x80, paddr=0xD000 + way * 0x1000,
                       tag_way=way, banks=banks, context=f"matrix hit {way}")
        # Miss -> replay (not handled).
        lp.transaction(vaddr=0x4000 + way * 0x80, paddr=0xD000 + way * 0x1000,
                       tag_match=False, tag_way=way, miss_handled=False,
                       context=f"matrix miss {way}")
        # Miss -> suppressed path (mshr full, not handled).
        lp.transaction(vaddr=0x4000 + way * 0x80, paddr=0xD000 + way * 0x1000,
                       tag_match=False, tag_way=way, mshr_full=True,
                       miss_handled=False, context=f"matrix suppressed {way}")
