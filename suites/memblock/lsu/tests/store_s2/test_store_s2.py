"""StoreUnitS2 UT: memory type, access fault and the SQ exception sideband."""
from __future__ import annotations

import random

import pytest

from lsuverify.common.robptr import LEVEL_FLUSH, LEVEL_FLUSH_AFTER
from lsuverify.store_s2.coverage import S2_CASES, StoreS2Coverage
from lsuverify.store_s2.env import (
    PBMT_DEFAULT,
    PBMT_IO,
    PBMT_NC,
    PBMT_PMA,
    PIPE_IN_FIELDS,
    StoreS2Env,
    random_pipe_in,
)

VADDR = 0x4000


@pytest.fixture
def s2(dut_factory):
    dut = dut_factory("store_s2")
    env = StoreS2Env(dut, StoreS2Coverage())
    env.reset()
    return env


def run(s2, in_valid=0, in_bits=None, pmp=None, redirect=None, context="cycle"):
    return s2.cycle(in_valid, in_bits or blank(), pmp or {"ld": 0, "st": 0, "mmio": 0},
                    redirect or {"valid": 0, "level": 0, "flag": 0, "value": 0,
                                 "former": 0},
                    context)


def blank():
    return {name: 0 for name in PIPE_IN_FIELDS}


def beat(instr_type=1, align=1, unalign_head=0, pbmt=PBMT_DEFAULT, tlb_hit=1,
         is_cbo=0, is_cbo_no_zero=0, has_exception=0, need_replay=0, rob=10,
         exc7=0, exc15=0, exc23=0, fullva=VADDR, **overrides):
    values = dict(
        accessType_instrType=instr_type, accessType_isCbo=is_cbo,
        accessType_isCboNoZero=is_cbo_no_zero, uop_exceptionVec_23=exc23,
        uop_exceptionVec_19=0, uop_exceptionVec_15=exc15, uop_exceptionVec_7=exc7,
        uop_exceptionVec_3=0, uop_trigger=0xF, uop_robIdx_flag=0,
        uop_robIdx_value=rob, uop_robIdx_isFormer=1, fullva=fullva, align=align,
        unalignHead=unalign_head, tlbHit=tlb_hit, tlbException_vaNeedExt=0,
        tlbException_isHyper=0, pbmt=pbmt, isForVSnonLeafPTE=0, gpaddr=0xAA,
        hasException=has_exception, needRSReplay=need_replay,
    )
    values.update(overrides)
    return values


# ------------------------------------------------------------------ pipeline
def test_idle_and_reset(s2):
    assert run(s2, context="idle")["out_valid"] == 0
    s2.coverage.sample_case("pipe.idle")
    assert int(s2.out_valid.value) == 0
    s2.coverage.sample_case("pipe.reset_clears_valid")


def test_fire_without_redirect(s2):
    got = run(s2, 1, beat(), context="fire")
    assert got["out_valid"] == 1
    assert got["toSqAddrRe_hasException"] == 0
    s2.coverage.sample_case("pipe.fire_without_redirect")


def test_redirect_kill(s2):
    got = run(s2, 1, beat(rob=10), redirect=dict(valid=1, level=LEVEL_FLUSH,
                                                 flag=0, value=10, former=1),
              context="kill")
    assert got["out_valid"] == 0
    s2.coverage.sample_case("pipe.killed_by_redirect")
    got = run(s2, 1, beat(rob=10), redirect=dict(valid=1, level=LEVEL_FLUSH_AFTER,
                                                 flag=0, value=11, former=1),
              context="younger")
    assert got["out_valid"] == 1
    s2.coverage.sample_case("pipe.clear_valid_for_younger_redirect")


def test_every_output_field_matches(s2):
    rng = random.Random(31)
    for cycle in range(60):
        got = run(s2, 1, random_pipe_in(rng, accessType_instrType=rng.choice([1, 2, 4]),
                                        pbmt=rng.randrange(4)),
                  pmp={"ld": rng.randrange(2), "st": rng.randrange(2),
                       "mmio": rng.randrange(2)},
                  context=f"field {cycle}")
        assert got["out_valid"] in (0, 1)
    s2.coverage.sample_case("pipe.field_fidelity")


# ------------------------------------------------------------------ memory type
@pytest.mark.parametrize("pbmt,pmp_mmio,want", [
    (PBMT_NC, 0, "nc_from_pbmt_one"),
    (PBMT_IO, 0, "mmio_from_pbmt_two"),
    (PBMT_PMA, 1, "mmio_from_pbmt_zero_and_pmp"),
    (PBMT_PMA, 0, "pma_is_normal"),
    (PBMT_DEFAULT, 0, "pbmt_default_is_normal"),
])
def test_memory_type_derivation(s2, pbmt, pmp_mmio, want):
    got = run(s2, 1, beat(pbmt=pbmt), pmp={"ld": 0, "st": 0, "mmio": pmp_mmio},
              context=want)
    if want.startswith("nc"):
        assert got["is_nc"] == 1
    elif want.startswith("mmio"):
        assert got["is_mmio"] == 1
    else:
        # Normal cacheable memory: neither non-cacheable nor MMIO.
        assert got["is_nc"] == 0 and got["is_mmio"] == 0
    s2.coverage.sample_case(f"memtype.{want}")


def test_memory_type_requires_tlb_hit_and_no_tlb_exception(s2):
    got = run(s2, 1, beat(pbmt=PBMT_NC, tlb_hit=0), context="no hit")
    assert got["is_nc"] == 0
    s2.coverage.sample_case("memtype.requires_tlb_hit")
    got = run(s2, 1, beat(pbmt=PBMT_NC, exc7=1), context="tlb exception")
    assert got["is_nc"] == 0
    got = run(s2, 1, beat(pbmt=PBMT_IO, exc23=1), context="gpf")
    assert got["is_mmio"] == 0
    s2.coverage.sample_case("memtype.blocked_by_tlb_exception")


def test_mem_back_type_follows_pmp_mmio(s2):
    got = run(s2, 1, beat(), pmp={"ld": 0, "st": 0, "mmio": 1}, context="mm")
    assert got["toSqAddrRe_memBackTypeMM"] == 0
    got = run(s2, 1, beat(), pmp={"ld": 0, "st": 0, "mmio": 0}, context="not mm")
    assert got["toSqAddrRe_memBackTypeMM"] == 1
    s2.coverage.sample_case("memtype.mem_back_type_mm_follows_pmp_mmio")
    got = run(s2, 1, beat(exc15=1), pmp={"ld": 0, "st": 0, "mmio": 1},
              context="mm but inaccessible")
    assert got["toSqAddrRe_memBackTypeMM"] == 1
    s2.coverage.sample_case("memtype.mem_back_type_mm_cleared_by_tlb_inaccessible")


# ------------------------------------------------------------------ exceptions
def test_pmp_store_denial_sets_access_fault(s2):
    got = run(s2, 1, beat(), pmp={"ld": 0, "st": 1, "mmio": 0}, context="pmp st")
    assert got["out_bits"]["uop_exceptionVec_7"] == 1
    assert got["out_bits"]["hasException"] == 1
    assert got["toSqAddrRe_hasException"] == 1
    s2.coverage.sample_case("exc.pmp_st_denies")


@pytest.mark.parametrize("is_cbo_no_zero,want", [(1, 1), (0, 0)])
def test_pmp_load_denial_only_applies_to_cbo_non_zero(s2, is_cbo_no_zero, want):
    got = run(s2, 1, beat(is_cbo=1, is_cbo_no_zero=is_cbo_no_zero),
              pmp={"ld": 1, "st": 0, "mmio": 0}, context="pmp ld")
    assert got["out_bits"]["uop_exceptionVec_7"] == want
    s2.coverage.sample_case("exc.pmp_ld_denies_only_cbo_nonzero")


def test_uncache_is_illegal_for_vectors_and_cbo(s2):
    got = run(s2, 1, beat(instr_type=2, pbmt=PBMT_NC), context="vector nc")
    assert got["out_bits"]["uop_exceptionVec_7"] == 1
    s2.coverage.sample_case("exc.vector_uncache_faults")
    got = run(s2, 1, beat(instr_type=1, is_cbo=1, pbmt=PBMT_IO), context="cbo io")
    assert got["out_bits"]["uop_exceptionVec_7"] == 1
    s2.coverage.sample_case("exc.cbo_uncache_faults")


def test_mmio_misaligned_is_access_fault(s2):
    got = run(s2, 1, beat(instr_type=1, align=0, pbmt=PBMT_IO), context="mmio misalign")
    assert got["out_bits"]["uop_exceptionVec_7"] == 1
    assert got["out_bits"]["uop_exceptionVec_6"] == 0
    s2.coverage.sample_case("exc.mmio_misaligned_faults")


def test_nc_misaligned_sets_misalign_not_access_fault(s2):
    got = run(s2, 1, beat(instr_type=1, align=0, pbmt=PBMT_NC), context="nc misalign")
    assert got["out_bits"]["uop_exceptionVec_6"] == 1
    assert got["out_bits"]["uop_exceptionVec_7"] == 0
    s2.coverage.sample_case("exc.nc_misaligned_sets_exception6")
    got = run(s2, 1, beat(instr_type=1, align=0, pbmt=PBMT_NC),
              pmp={"ld": 0, "st": 1, "mmio": 0}, context="nc misalign pmp")
    assert got["out_bits"]["uop_exceptionVec_6"] == 0
    assert got["out_bits"]["uop_exceptionVec_7"] == 1
    s2.coverage.sample_case("exc.nc_misaligned_pmp_denied_is_not_exception6")


def test_exception_passthrough(s2):
    got = run(s2, 1, beat(has_exception=1, exc15=1), context="passthrough")
    assert got["out_bits"]["hasException"] == 1
    assert got["out_bits"]["uop_exceptionVec_15"] == 1
    assert got["toSqAddrRe_hasException"] == 1
    s2.coverage.sample_case("exc.passthrough_has_exception")
    s2.coverage.sample_case("exc.passthrough_exception_bits")


# ---------------------------------------------------------------- toSqAddrRe
def test_to_sq_addr_re_is_combinational(s2):
    got = run(s2, 1, beat(has_exception=0), context="sqre")
    assert got["toSqAddrRe_hasException"] == 0
    got = run(s2, 1, beat(has_exception=1), context="sqre exc")
    assert got["toSqAddrRe_hasException"] == 1
    s2.coverage.sample_case("sqre.valid_is_fire")
    got = run(s2, 1, beat(has_exception=1, rob=10),
              redirect=dict(valid=1, level=LEVEL_FLUSH, flag=0, value=10, former=1),
              context="killed exc")
    assert got["toSqAddrRe_hasException"] == 0
    s2.coverage.sample_case("sqre.has_exception_gated_by_fire")


def test_last_request_and_head_tlb_hit(s2):
    got = run(s2, 1, beat(unalign_head=1), context="head")
    assert got["toSqAddrRe_isLastRequest"] == 0
    assert got["unalignHeadTlbHit"] == 1
    s2.coverage.sample_case("sqre.last_request_from_head")
    s2.coverage.sample_case("head.tlb_hit_needs_fire_head_and_tlb_hit")
    got = run(s2, 1, beat(unalign_head=1, tlb_hit=0), context="head no hit")
    assert got["unalignHeadTlbHit"] == 0
    got = run(s2, 1, beat(unalign_head=0), context="no head")
    assert got["unalignHeadTlbHit"] == 0
    got = run(s2, 1, beat(unalign_head=1, rob=10),
              redirect=dict(valid=1, level=LEVEL_FLUSH, flag=0, value=10, former=1),
              context="head killed")
    assert got["unalignHeadTlbHit"] == 0


def test_seeded_random_stream_matches_the_model(s2):
    rng = random.Random(20261025)
    for cycle in range(400):
        in_valid = 1 if rng.random() < 0.8 else 0
        values = random_pipe_in(rng, accessType_instrType=rng.choice([1, 1, 2, 4]),
                                pbmt=rng.randrange(4))
        pmp = {"ld": rng.randrange(2), "st": rng.randrange(2), "mmio": rng.randrange(2)}
        redir = {"valid": 0, "level": 0, "flag": 0, "value": 0, "former": 0}
        if rng.random() < 0.2:
            redir = dict(valid=1, level=rng.randrange(2), flag=rng.randrange(2),
                         value=rng.randrange(160), former=rng.randrange(2))
        run(s2, in_valid, values, pmp, redir, context=f"random {cycle}")


def test_case_inventory_is_exact():
    assert len(S2_CASES) == len(set(S2_CASES))
    assert len(S2_CASES) == 28
