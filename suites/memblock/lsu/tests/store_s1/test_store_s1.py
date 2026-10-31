"""StoreUnitS1 UT: physical address, exception formation and SQ address write."""
from __future__ import annotations

import random

import pytest

from suites.memblock.lsu.pointers import LEVEL_FLUSH, LEVEL_FLUSH_AFTER
from suites.memblock.lsu.store_s1.coverage import S1_CASES, StoreS1Coverage
from suites.memblock.lsu.store_s1.env import (
    PIPE_IN_FIELDS,
    TLB_RESP_FIELDS,
    StoreS1Env,
    blank,
    blank_redirect,
    blank_trigger,
    random_pipe_in,
    random_tlb,
    tail_mask,
)
from suites.memblock.lsu.store_trigger.env import (
    ACTION_BREAKPOINT,
    ACTION_CODE_BREAKPOINT,
    ACTION_CODE_DEBUG,
    ACTION_DEBUG,
    ACTION_NONE,
    MATCH_EQ,
    TRIGGER_NUM,
    TriggerConfig,
)

PADDR = 0x1234_5000
VADDR = 0x2000


@pytest.fixture
def s1(dut_factory):
    dut = dut_factory("store_s1")
    env = StoreS1Env(dut, StoreS1Coverage())
    env.reset()
    return env


def run(s1, in_valid=0, in_bits=None, tlb=None, tlb_valid=1, redirect=None,
        cfg=None, enables=None, debug=0, bp_exp=1, head_hit=1, queue_ready=1,
        context="cycle"):
    return s1.cycle(in_valid, in_bits or blank(PIPE_IN_FIELDS),
                    tlb if tlb is not None else blank(TLB_RESP_FIELDS),
                    tlb_valid, redirect or blank_redirect(),
                    cfg or blank_trigger(),
                    enables if enables is not None else [1] * TRIGGER_NUM,
                    debug, bp_exp, head_hit, queue_ready, context)


def beat(entrance=0x8, instr_type=1, rob=10, sq=5, size=3, mask=0xFF,
         vaddr=VADDR, unalign_head=0, cross4k=0, align=1, illegal=0,
         addr_ready=0, is_cbo=0, fu=None, **overrides):
    values = dict(
        entrance=entrance, accessType_instrType=instr_type, accessType_isCbo=is_cbo,
        accessType_isCboNoZero=0, uop_exceptionVec_19=0, uop_isRVC=0,
        uop_ftqPtr_flag=0, uop_ftqPtr_value=0, uop_ftqOffset=0,
        uop_fuOpType=fu if fu is not None else ((size & 7) << 1),
        uop_robIdx_flag=0, uop_robIdx_value=rob, uop_robIdx_isFormer=1,
        uop_sqIdx_first_flag=0, uop_sqIdx_second_flag=0, uop_sqIdx_value=sq,
        vaddr=vaddr, fullva=vaddr + 0x1000, size=size, mask=mask,
        illegalIssue=illegal, ssid=0x11, storeSetHit=1,
        align=align, unalignHead=unalign_head, cross4KPage=cross4k,
        isAddrReadyHead=addr_ready,
    )
    values.update(overrides)
    return values


def tlb(paddr=PADDR, miss=0, fullva=0x3000, hyper=0, pbmt=1, pf_st=0, pf_ld=0,
        af_st=0, af_ld=0, gpf_st=0, gpf_ld=0, va_need_ext=0, non_leaf=0):
    return dict(paddr_0=paddr, gpaddr_0=0xAA00, fullva=fullva, pbmt_0=pbmt,
                miss=miss, isForVSnonLeafPTE=non_leaf, excp_0_vaNeedExt=va_need_ext,
                excp_0_isHyper=hyper, excp_0_gpf_ld=gpf_ld, excp_0_gpf_st=gpf_st,
                excp_0_pf_ld=pf_ld, excp_0_pf_st=pf_st, excp_0_af_ld=af_ld,
                excp_0_af_st=af_st)


# ------------------------------------------------------------------ pipeline
def test_idle_and_reset(s1):
    assert run(s1, context="idle")["out_valid"] == 0
    s1.coverage.sample_case("pipe.idle")
    assert int(s1.out_valid.value) == 0
    s1.coverage.sample_case("pipe.reset_clears_valid")


def test_normal_beat_registers(s1):
    got = run(s1, 1, beat(), tlb(), context="register")
    assert got["out_valid"] == 1
    assert got["tlbReqKill"] == 0
    s1.coverage.sample_case("pipe.normal_beat_registers")
    assert run(s1, 0, context="drain")["out_valid"] == 0


def test_every_pipe_out_field_matches(s1):
    rng = random.Random(21)
    for cycle in range(40):
        values = random_pipe_in(rng, entrance=0x8, accessType_instrType=1)
        got = run(s1, 1, values, random_tlb(rng, miss=0),
                  redirect=blank_redirect(), context=f"field {cycle}")
        assert got["out_valid"] in (0, 1)
    s1.coverage.sample_case("pipe.field_fidelity")


# ---------------------------------------------------------------------- kills
@pytest.mark.parametrize("case,valid", [
    ("redirect_same_slot", 0), ("redirect_after_slot", 0),
    ("redirect_younger", 1), ("redirect_invalid", 1), ("redirect_former", 1),
])
def test_redirect_kill_matrix(s1, case, valid):
    redir = {
        "redirect_same_slot": dict(valid=1, flag=0, value=10, former=1, level=LEVEL_FLUSH),
        "redirect_after_slot": dict(valid=1, flag=0, value=9, former=1, level=LEVEL_FLUSH_AFTER),
        "redirect_younger": dict(valid=1, flag=0, value=11, former=1, level=LEVEL_FLUSH_AFTER),
        "redirect_invalid": dict(valid=0, flag=0, value=10, former=1, level=LEVEL_FLUSH),
        "redirect_former": dict(valid=1, flag=0, value=10, former=0, level=LEVEL_FLUSH_AFTER),
    }[case]
    got = run(s1, 1, beat(rob=10), tlb(), redirect=redir, context=case)
    assert got["out_valid"] == valid
    s1.coverage.sample_case({
        "redirect_same_slot": "kill.redirect_same_slot",
        "redirect_after_slot": "kill.redirect_after_slot",
        "redirect_younger": "kill.redirect_younger_survives",
        "redirect_invalid": "kill.redirect_invalid_survives",
        "redirect_former": "kill.redirect_former_ordering",
    }[case])


def test_illegal_issue_kills_even_without_redirect(s1):
    got = run(s1, 1, beat(illegal=1), tlb(), context="illegal")
    assert got["out_valid"] == 0
    assert got["tlbReqKill"] == 1
    s1.coverage.sample_case("kill.illegal_issue")
    s1.coverage.sample_case("kill.illegal_issue_without_redirect")
    s1.coverage.sample_case("kill.tlb_req_kill_follows_kill")


def test_young_cross_head_needs_addr_ready(s1):
    got = run(s1, 1, beat(unalign_head=1, cross4k=1, addr_ready=0), tlb(),
              context="young head")
    assert got["out_valid"] == 0
    s1.coverage.sample_case("kill.young_cross_head")
    got = run(s1, 1, beat(unalign_head=1, cross4k=1, addr_ready=1), tlb(),
              context="addr ready")
    assert got["out_valid"] == 1
    s1.coverage.sample_case("kill.young_cross_head_not_needed_when_addr_ready")


# ---------------------------------------------------------------- TLB response
def test_tlb_hit_miss_and_no_response(s1):
    got = run(s1, 1, beat(), tlb(miss=0), context="hit")
    assert got["out_bits"]["tlbHit"] == 1
    s1.coverage.sample_case("tlb.hit")
    got = run(s1, 1, beat(), tlb(miss=1), context="miss")
    assert got["out_bits"]["tlbHit"] == 0
    assert got["out_bits"]["pbmt"] == 0
    s1.coverage.sample_case("tlb.miss")
    s1.coverage.sample_case("tlb.pbmt_zeroed_on_miss")
    got = run(s1, 1, beat(), tlb(), tlb_valid=0, context="no resp")
    assert got["out_bits"]["tlbHit"] == 0
    s1.coverage.sample_case("tlb.no_response")


# ------------------------------------------------------------------ exceptions
@pytest.mark.parametrize("field,bit", [
    ("pf_st", "uop_exceptionVec_15"), ("pf_ld", "uop_exceptionVec_15"),
    ("af_st", "uop_exceptionVec_7"), ("af_ld", "uop_exceptionVec_7"),
    ("gpf_st", "uop_exceptionVec_23"), ("gpf_ld", "uop_exceptionVec_23"),
])
def test_tlb_exceptions_map_to_fixed_bits(s1, field, bit):
    got = run(s1, 1, beat(), tlb(**{field: 1}), context=field)
    assert got["out_bits"][bit] == 1
    assert got["out_bits"]["hasException"] == 1
    s1.coverage.sample_case({
        "uop_exceptionVec_15": "exc.pf_from_either_field",
        "uop_exceptionVec_7": "exc.af_from_either_field",
        "uop_exceptionVec_23": "exc.gpf_from_either_field",
    }[bit])


def test_exceptions_require_a_tlb_hit(s1):
    got = run(s1, 1, beat(), tlb(pf_st=1, miss=1), context="miss with pf")
    assert got["out_bits"]["uop_exceptionVec_15"] == 0
    assert got["out_bits"]["hasException"] == 0
    s1.coverage.sample_case("exc.exceptions_require_tlb_hit")


def test_trigger_actions_set_exception_bits(s1):
    cfg = blank_trigger()
    cfg[0] = TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR,
                           action=ACTION_CODE_BREAKPOINT)
    got = run(s1, 1, beat(), tlb(), cfg=cfg, context="breakpoint")
    assert got["out_bits"]["uop_exceptionVec_3"] == 1
    assert got["out_bits"]["hasException"] == 1
    s1.coverage.sample_case("exc.breakpoint_from_trigger_action_zero")
    s1.coverage.sample_case("trigger.trigger_goes_to_pipe_out")

    cfg[0] = TriggerConfig(match_type=MATCH_EQ, tdata2=VADDR,
                           action=ACTION_CODE_DEBUG)
    got = run(s1, 1, beat(), tlb(), cfg=cfg, context="debug")
    assert got["out_bits"]["uop_exceptionVec_3"] == 0
    assert got["out_bits"]["hasException"] == 1
    assert got["out_bits"]["uop_trigger"] == ACTION_DEBUG
    s1.coverage.sample_case("exc.debug_mode_from_trigger_action_one")

    got = run(s1, 1, beat(), tlb(), cfg=blank_trigger(), context="none")
    assert got["out_bits"]["hasException"] == 0
    assert got["out_bits"]["uop_trigger"] == ACTION_NONE
    s1.coverage.sample_case("exc.no_exception")


# ------------------------------------------------------------------ SQ address
def test_sq_address_base_fields(s1):
    got = run(s1, 1, beat(vaddr=VADDR, size=3, mask=0xFF, sq=9), tlb(paddr=PADDR),
              context="base")
    assert got["toSqAddr_valid"] == 1
    bits = got["toSqAddr_bits"]
    assert bits["vaddr"] == VADDR
    assert bits["paddr"] == PADDR
    assert bits["size"] == 3
    assert bits["mask"] == 0xFF
    assert bits["uop_sqIdx_value"] == 9
    assert bits["isUnalign"] == 0
    assert bits["cross16Byte"] == 0
    assert bits["isLastRequest"] == 1
    s1.coverage.sample_case("sqaddr.base_fields")


def test_sq_address_cbo_normalisation(s1):
    got = run(s1, 1, beat(vaddr=VADDR + 5, is_cbo=1, size=2, fu=(2 << 1) | 1),
              tlb(paddr=PADDR + 7), context="cbo")
    bits = got["toSqAddr_bits"]
    assert bits["vaddr"] == (VADDR + 5) & ~0xF
    assert bits["paddr"] == (PADDR + 7) & ~0xF
    assert bits["size"] == 4
    assert bits["wlineflag"] == 1
    s1.coverage.sample_case("sqaddr.cbo_aligns_vaddr_and_paddr")
    s1.coverage.sample_case("sqaddr.cbo_forces_size_qb_and_wline")
    s1.coverage.sample_case("trigger.cbo_mode")


def test_sq_address_tlb_miss_unalign_and_cross_flags(s1):
    got = run(s1, 1, beat(tlb_miss := 0, align=0, unalign_head=0), tlb(miss=1),
              context="tlb miss")
    assert got["toSqAddr_bits"]["tlbMiss"] == 1
    s1.coverage.sample_case("sqaddr.tlb_miss_flag")
    got = run(s1, 1, beat(align=0), tlb(), context="unalign")
    assert got["toSqAddr_bits"]["isUnalign"] == 1
    s1.coverage.sample_case("sqaddr.unalign_flag")
    got = run(s1, 1, beat(entrance=0x1), tlb(), context="tail entrance")
    assert got["toSqAddr_bits"]["cross16Byte"] == 1
    got = run(s1, 1, beat(unalign_head=1), tlb(), context="head")
    assert got["toSqAddr_bits"]["cross16Byte"] == 1
    assert got["toSqAddr_bits"]["isLastRequest"] == 0
    s1.coverage.sample_case("sqaddr.cross16_from_entrance_or_head")
    s1.coverage.sample_case("sqaddr.last_request_from_head")


def test_sq_address_is_suppressed_for_prefetch(s1):
    got = run(s1, 1, beat(instr_type=4), tlb(), context="prefetch")
    assert got["toSqAddr_valid"] == 0
    s1.coverage.sample_case("sqaddr.suppressed_for_prefetch")


# -------------------------------------------------------------- STA nuke query
def test_nuke_query_requires_fire_and_tlb_hit(s1):
    got = run(s1, 1, beat(mask=0x0F0F), tlb(paddr=PADDR), context="nuke")
    assert got["staNukeQueryReq_valid"] == 1
    bits = got["staNukeQueryReq_bits"]
    assert bits["paddr"] == PADDR
    assert bits["mask"] == 0x0F0F
    assert bits["matchType"] == 0
    s1.coverage.sample_case("nuke.issued_on_fire_and_tlb_hit")
    s1.coverage.sample_case("nuke.match_type_word_for_normal")
    got = run(s1, 1, beat(mask=0x0F0F), tlb(miss=1), context="nuke miss")
    assert got["staNukeQueryReq_valid"] == 0
    s1.coverage.sample_case("nuke.suppressed_without_tlb_hit")
    got = run(s1, 1, beat(instr_type=4), tlb(), context="nuke prefetch")
    assert got["staNukeQueryReq_valid"] == 0
    s1.coverage.sample_case("nuke.suppressed_for_prefetch")


def test_nuke_match_type_is_cacheline_for_cbo(s1):
    got = run(s1, 1, beat(is_cbo=1), tlb(), context="nuke cbo")
    assert got["staNukeQueryReq_valid"] == 1
    assert got["staNukeQueryReq_bits"]["matchType"] == 2
    s1.coverage.sample_case("nuke.match_type_cacheline_for_cbo")


# --------------------------------------------------------------- unaligned tail
def test_unaligned_tail_injection(s1):
    vaddr = 0x100C
    got = run(s1, 1, beat(vaddr=vaddr, unalign_head=1, size=3, mask=0xFF00),
              tlb(fullva=0x8000), context="tail")
    assert got["unalignTail_valid"] == 1
    bits = got["unalignTail_bits"]
    assert bits["vaddr"] == 0x1010
    assert bits["fullva"] == 0x8010
    assert bits["size"] == 3
    s1.coverage.sample_case("tail.injected_on_head")
    s1.coverage.sample_case("tail.next_16b_address")
    s1.coverage.sample_case("tail.fullva_from_tlb_response")
    # 8B store at offset 12 covers bytes 12..19, so the second 16B word holds
    # the four bytes 16..19.
    assert bits["mask"] == tail_mask(vaddr, (3 << 1))
    assert bits["mask"] == 0xF
    got = run(s1, 1, beat(vaddr=0x100E, unalign_head=1, size=2, mask=0xC000),
              tlb(), context="tail2")
    assert got["unalignTail_bits"]["mask"] == tail_mask(0x100E, (2 << 1))
    s1.coverage.sample_case("tail.mask_high_half")
    got = run(s1, 1, beat(unalign_head=0), tlb(), context="no tail")
    assert got["unalignTail_valid"] == 0
    s1.coverage.sample_case("tail.not_injected_without_head")


# -------------------------------------------------------------- unaligned queue
def test_unaligned_queue_request_conditions(s1):
    got = run(s1, 1, beat(entrance=0x1, cross4k=1), tlb(), head_hit=1,
              queue_ready=1, context="queue")
    assert got["toUnalignQueue_valid"] == 1
    assert got["toUnalignQueue_bits"]["paddr"] == PADDR
    s1.coverage.sample_case("queue.requires_tail_entrance_and_cross_page")
    s1.coverage.sample_case("queue.requires_both_tlb_hits")
    got = run(s1, 1, beat(entrance=0x1, cross4k=1), tlb(), head_hit=0,
              context="queue no head hit")
    assert got["toUnalignQueue_valid"] == 0
    got = run(s1, 1, beat(entrance=0x1, cross4k=0), tlb(), context="queue no cross")
    assert got["toUnalignQueue_valid"] == 0
    s1.coverage.sample_case("queue.not_for_scalar_only")


def test_unaligned_queue_ready_only_affects_feedback(s1):
    got = run(s1, 1, beat(entrance=0x1, cross4k=1), tlb(), queue_ready=0,
              context="queue not ready")
    assert got["toUnalignQueue_valid"] == 1
    assert got["feedBackSlow_valid"] == 1
    assert got["feedBackSlow_hit"] == 0
    s1.coverage.sample_case("queue.requires_ready")


# ---------------------------------------------------------------- RS feedback
def test_scalar_feedback_tracks_the_tlb_response(s1):
    got = run(s1, 1, beat(), tlb(miss=0), context="fb hit")
    assert got["feedBackSlow_valid"] == 1
    assert got["feedBackSlow_hit"] == 1
    s1.coverage.sample_case("feedback.scalar_fire_without_head")
    s1.coverage.sample_case("feedback.hit_equals_tlb_hit")
    got = run(s1, 1, beat(), tlb(miss=1), context="fb miss")
    assert got["feedBackSlow_valid"] == 1
    assert got["feedBackSlow_hit"] == 0
    assert got["out_bits"]["needRSReplay"] == 1
    s1.coverage.sample_case("feedback.need_rs_replay_bit")


def test_unaligned_tail_feedback_needs_both_responses(s1):
    got = run(s1, 1, beat(entrance=0x1, cross4k=0), tlb(), head_hit=1,
              context="tail both hit")
    assert got["feedBackSlow_hit"] == 1
    s1.coverage.sample_case("feedback.tail_requires_both_hits")
    got = run(s1, 1, beat(entrance=0x1, cross4k=0), tlb(), head_hit=0,
              context="tail head miss")
    assert got["feedBackSlow_hit"] == 0
    got = run(s1, 1, beat(entrance=0x1, cross4k=1), tlb(), head_hit=1,
              queue_ready=0, context="tail cross page blocked")
    assert got["feedBackSlow_hit"] == 0
    s1.coverage.sample_case("feedback.tail_cross_page_requires_queue_ready")


def test_force_replay_on_illegal_issue_and_young_cross_head(s1):
    got = run(s1, 1, beat(illegal=1), tlb(), context="force illegal")
    assert got["feedBackSlow_valid"] == 1
    assert got["feedBackSlow_hit"] == 0
    assert got["out_bits"]["needRSReplay"] == 1
    s1.coverage.sample_case("feedback.force_replay_on_illegal_issue")
    got = run(s1, 1, beat(unalign_head=1, cross4k=1, addr_ready=0), tlb(),
              context="force young head")
    assert got["feedBackSlow_valid"] == 1
    assert got["feedBackSlow_hit"] == 0
    s1.coverage.sample_case("feedback.force_replay_on_young_cross_head")


def test_vector_beat_gets_no_feedback(s1):
    got = run(s1, 1, beat(instr_type=2), tlb(), context="vector")
    assert got["feedBackSlow_valid"] == 0
    s1.coverage.sample_case("feedback.not_for_vector")
    got = run(s1, 1, beat(unalign_head=1), tlb(), context="head beat")
    assert got["feedBackSlow_valid"] == 0
    s1.coverage.sample_case("feedback.not_for_head_beat")


# -------------------------------------------------------------------- LFST
def test_lfst_update_conditions(s1):
    got = run(s1, 1, beat(sq=6, ssid=0x2A), tlb(), context="lfst")
    assert got["updateLFST_valid"] == 1
    assert got["updateLFST_bits"]["sqIdx_value"] == 6
    assert got["updateLFST_bits"]["ssid"] == 0x2A
    assert got["updateLFST_bits"]["storeSetHit"] == 1
    s1.coverage.sample_case("lfst.updated_for_scalar_cacheable")
    got = run(s1, 1, beat(instr_type=4), tlb(), context="lfst prefetch")
    assert got["updateLFST_valid"] == 0
    s1.coverage.sample_case("lfst.not_for_prefetch")
    got = run(s1, 1, beat(entrance=0x1), tlb(), context="lfst tail")
    assert got["updateLFST_valid"] == 0
    s1.coverage.sample_case("lfst.not_for_tail")
    got = run(s1, 1, beat(), tlb(miss=1), context="lfst miss")
    assert got["updateLFST_valid"] == 0
    s1.coverage.sample_case("lfst.requires_tlb_hit")


# ----------------------------------------------------------------- trigger
def test_trigger_vector_stride_detection(s1):
    """``isVectorUnitStride = instrType[1] & (fuOpType[6:5] == 0)``."""
    cfg = blank_trigger()
    cfg[0] = TriggerConfig(match_type=MATCH_EQ, tdata2=(VADDR & ~0xF) | 0x2,
                           action=ACTION_CODE_DEBUG)
    vector = beat(instr_type=2, fu=(0 << 1), mask=1 << 2, vaddr=VADDR)
    got = run(s1, 1, vector, tlb(), cfg=cfg, context="vector stride")
    assert got["out_bits"]["uop_trigger"] == ACTION_DEBUG
    s1.coverage.sample_case("trigger.vector_stride_detection")
    # Same mask but fuOpType[6:5]!=0 disables the vector-stride path entirely.
    vector_no_stride = beat(instr_type=2, fu=(1 << 5), mask=1 << 2, vaddr=VADDR)
    got = run(s1, 1, vector_no_stride, tlb(), cfg=cfg, context="no stride")
    assert got["out_bits"]["uop_trigger"] == ACTION_NONE


# -------------------------------------------------------------------- random
def test_seeded_random_stream_matches_the_model(s1):
    rng = random.Random(20261025)
    for cycle in range(400):
        in_valid = 1 if rng.random() < 0.8 else 0
        values = random_pipe_in(rng, entrance=rng.choice([0x1, 0x2, 0x8]),
                                accessType_instrType=rng.choice([1, 1, 2, 4]))
        response = random_tlb(rng, miss=1 if rng.random() < 0.2 else 0)
        redir = blank_redirect()
        if rng.random() < 0.25:
            redir = dict(valid=1, level=rng.randrange(2), flag=rng.randrange(2),
                         value=rng.randrange(160), former=rng.randrange(2))
        cfg = [
            TriggerConfig(match_type=rng.choice([0, 2, 3]),
                          select=1 if rng.random() < 0.1 else 0,
                          timing=rng.randrange(2),
                          action=rng.choice([0, 1, 2, 15]),
                          chain=1 if rng.random() < 0.2 else 0,
                          store=1 if rng.random() < 0.9 else 0,
                          tdata2=rng.randrange(1 << 50))
            for _ in range(TRIGGER_NUM)
        ]
        run(s1, in_valid, values, response,
            tlb_valid=1 if rng.random() < 0.85 else 0, redirect=redir,
            cfg=cfg, enables=[1 if rng.random() < 0.8 else 0 for _ in range(TRIGGER_NUM)],
            debug=1 if rng.random() < 0.05 else 0,
            bp_exp=1 if rng.random() < 0.7 else 0,
            head_hit=rng.randrange(2), queue_ready=rng.randrange(2),
            context=f"random {cycle}")


def test_case_inventory_is_exact():
    assert len(S1_CASES) == len(set(S1_CASES))
    assert len(S1_CASES) == 63


def test_tail_mask_helper_matches_the_documented_relation():
    assert tail_mask(0x100C, 3 << 1) == 0xF     # 8B store at offset 12
    assert tail_mask(0x100E, 2 << 1) == 0x3     # 4B store at offset 14
    assert tail_mask(0x1008, 3 << 1) == 0x0     # 8B store at offset 8 does not cross
    # genVWmask takes size[1:0], so Q sizes alias to B/H/W/D bases.
    assert tail_mask(0x1001, 4 << 1) == tail_mask(0x1001, 0 << 1)


# ------------------------------------------------------- full-width toggling
def test_trigger_tdata2_full_width_for_every_slot(s1):
    """Walk one bit across all 64 tdata2 bits of each of the four slots."""
    for slot in range(TRIGGER_NUM):
        for bit in range(64):
            cfg = blank_trigger()
            cfg[slot] = TriggerConfig(match_type=MATCH_EQ, tdata2=1 << bit,
                                      action=ACTION_CODE_DEBUG)
            run(s1, 1, beat(), tlb(), cfg=cfg, context=f"tdata2 slot{slot} bit{bit}")
        cfg = blank_trigger()
        cfg[slot] = TriggerConfig(match_type=MATCH_EQ, tdata2=0)
        run(s1, 1, beat(), tlb(), cfg=cfg, context=f"tdata2 slot{slot} clear")


def test_tail_address_full_width(s1):
    """The tail address is ``(vaddr >> 4) + 1 << 4`` and ``(fullva >> 4) + 1 << 4``."""
    for bit in range(4, 50):
        got = run(s1, 1, beat(vaddr=1 << bit, unalign_head=1), tlb(),
                  context=f"tail vaddr bit{bit}")
        assert got["unalignTail_valid"] == 1
    for bit in range(4, 64):
        got = run(s1, 1, beat(vaddr=0, unalign_head=1), tlb(fullva=1 << bit),
                  context=f"tail fullva bit{bit}")
        assert got["unalignTail_valid"] == 1
    run(s1, 1, beat(vaddr=0, unalign_head=1), tlb(fullva=0), context="tail clear")


def test_tail_mask_walks_every_reachable_bit(s1):
    """``mask = ((base << vaddr[3:0]) >> 16) & 0x7F``.

    With an 8B base (0x00FF) and offsets 9..15 the shifted high half becomes
    1, 3, 7, 0xF, 0x1F, 0x3F, 0x7F, which toggles every reachable mask bit.
    """
    seen = set()
    for offset in range(9, 16):
        got = run(s1, 1, beat(vaddr=offset, unalign_head=1, size=3), tlb(),
                  context=f"tail mask offset {offset}")
        seen.add(got["unalignTail_bits"]["mask"])
    assert seen == {0x1, 0x3, 0x7, 0xF, 0x1F, 0x3F, 0x7F}
    for size in (0, 1, 2):
        run(s1, 1, beat(vaddr=0xF, unalign_head=1, size=size), tlb(),
            context=f"tail mask size {size}")
    run(s1, 1, beat(vaddr=0, unalign_head=1, size=0), tlb(), context="tail mask clear")


def test_entrance_vector_value_is_a_boundary_only_input(s1):
    """``entrance=0x4`` (vectorIssue) has no producer in this configuration, but
    the port is a plain input; driving it documents the actual behaviour: it
    takes the non-tail feedback path."""
    got = run(s1, 1, beat(entrance=0x4), tlb(), context="entrance 0x4")
    assert got["updateLFST_valid"] == 1
    assert got["feedBackSlow_valid"] == 1
    got = run(s1, 1, beat(entrance=0x2), tlb(), context="entrance 0x2")
    assert got["toSqAddr_valid"] == 1
