"""LoadUnitS0 UT: request synthesis, arbitration, TLB/DCache/forward requests."""
from __future__ import annotations

import random

import pytest

from suites.memblock.lsu.load_s0.coverage import CASES, LoadS0Coverage
from suites.memblock.lsu.load_s0.env import (
    FAST_FIELDS,
    LDIN_FIELDS,
    REPLAY_FIELDS,
    UNALIGN_FIELDS,
    LoadS0Env,
    blank_inputs,
    gen_vwmask,
    is_aligned,
    ldin_payload,
    random_fast,
    random_ldin,
    random_replay,
    random_unalign,
    sext,
)

LD = 0x06           # size 3 (8B)
LW = 0x04           # size 2
LH = 0x02           # size 1
LB = 0x00           # size 0
LD16 = 0x08         # size 4 (16B)


@pytest.fixture
def s0(dut_factory):
    dut = dut_factory("load_s0")
    env = LoadS0Env(dut, LoadS0Coverage())
    env.reset()
    return env


# ------------------------------------------------------------------ helpers
def unalign_bits(**overrides):
    # A tail injection normally belongs to a scalar load, so the S0 wakeup path
    # (``accessType_instrType[0]``) is live unless a test says otherwise.
    bits = {name: 0 for name in UNALIGN_FIELDS}
    bits["accessType_instrType"] = 1
    bits.update(overrides)
    return bits


def replay_bits(**overrides):
    bits = {name: 0 for name in REPLAY_FIELDS}
    bits.update(overrides)
    return bits


def fast_bits(**overrides):
    bits = {name: 0 for name in FAST_FIELDS}
    bits.update(overrides)
    return bits


def ldin_bits(fu=LD, src0=0x8000_1000, imm=0, **overrides):
    bits = {name: 0 for name in LDIN_FIELDS}
    bits.update({"fuOpType": fu, "src_0": src0, "imm": imm})
    bits.update(overrides)
    return bits


def make(unalign=None, replay=None, fast=None, ldin=None, ready=1):
    """Build one input bundle; an omitted lane is idle with zero payload."""
    inputs = blank_inputs()
    inputs["dcache_ready"] = ready
    if unalign is not None:
        inputs["unalign"]["valid"] = 1
        inputs["unalign"]["bits"] = unalign
    if replay is not None:
        inputs["replay"]["valid"] = 1
        inputs["replay"]["bits"] = replay
    if fast is not None:
        inputs["fast"]["valid"] = 1
        inputs["fast"]["bits"] = fast
    if ldin is not None:
        inputs["ldin"]["valid"] = 1
        inputs["ldin"]["bits"] = ldin
    return inputs


def run(s0, inputs, context="cycle"):
    return s0.cycle(inputs, context)


# ------------------------------------------------------------------- lanes
def test_unalign_tail_payload_passes_through_as_a_q_access(s0):
    bits = unalign_bits(uop_pdest=0x5A, vaddr=0x1234_5678, fullva=0xDEAD_BEEF,
                        mask=0x00FF, uop_lqIdx_value=7)
    got = run(s0, make(unalign=bits), "unalign passthrough")
    out = got["pipeOut_bits"]
    assert got["pipeOut_valid"] == 1
    assert out["entrance"] == 0x01
    assert out["size"] == 4, "the arbiter forces the tail lane to a Q access"
    assert out["noQuery"] == 0, "the arbiter forces the tail lane query bit to 0"
    assert out["uop_pdest"] == 0x5A
    assert out["vaddr"] == 0x1234_5678
    assert out["fullva"] == 0xDEAD_BEEF
    assert out["mask"] == 0x00FF
    assert out["uop_lqIdx_value"] == 7
    s0.coverage.sample_case("lane.unalign_tail_passthrough")


def test_each_lane_gets_its_entrance_code(s0):
    replay_hi = replay_bits(entrance=0x02)
    replay_lo = replay_bits(entrance=0x08)
    fast = fast_bits(entrance=0x30)
    cases = [
        ("replay hi", make(replay=replay_hi), 0x02),
        ("replay lo", make(replay=replay_lo), 0x08),
        ("fast", make(fast=fast), 0x34),
        ("scalar", make(ldin=ldin_bits()), 0x40),
    ]
    for label, inputs, entrance in cases:
        got = run(s0, inputs, label)
        assert got["pipeOut_valid"] == 1, label
        assert got["pipeOut_bits"]["entrance"] == entrance, label
    s0.coverage.sample_case("lane.entrance_codes")


def test_scalar_address_size_and_mask_are_synthesized(s0):
    # LD (8B) at src 0x1000 + imm 0x0C: mask = 0xFF << 12, size = 3.
    got = run(s0, make(ldin=ldin_bits(fu=LD, src0=0x8000_1000, imm=0x0C)),
              "scalar LD")
    out = got["pipeOut_bits"]
    assert out["vaddr"] == 0x8000_100C
    assert out["fullva"] == 0x8000_100C
    assert out["size"] == 3
    assert out["mask"] == 0xF000
    assert out["accessType_instrType"] == 1
    assert out["accessType_pftType"] == 2
    assert out["noQuery"] == 0
    s0.coverage.sample_case("lane.scalar_address_and_mask")
    # Negative immediate sign extends into the 50-bit vaddr and the 64-bit fullva.
    got = run(s0, make(ldin=ldin_bits(fu=LW, src0=0x100, imm=0xFF8)),
              "scalar negative imm")
    assert got["pipeOut_bits"]["vaddr"] == 0x100 - 8
    assert got["pipeOut_bits"]["fullva"] == (0x100 - 8) & ((1 << 64) - 1)
    assert got["pipeOut_bits"]["mask"] == 0xF00
    # The mask is the byte mask shifted inside the 16B word.
    assert gen_vwmask(3, 0x100C) == 0xF000
    assert gen_vwmask(3, 0x1000) == 0x00FF


def test_scalar_prefetch_i_only_probes_the_tlb(s0):
    # Start from a normal load so the noQuery / pftType pins toggle both ways.
    run(s0, make(ldin=ldin_bits(fu=LD, src0=0x2000, imm=0x10)), "scalar setup")
    got = run(s0, make(ldin=ldin_bits(fu=0x01, src0=0x2000, imm=0x10)),
              "prefetch_i")
    out = got["pipeOut_bits"]
    assert out["accessType_instrType"] == 4
    assert out["accessType_pftType"] == 3
    assert out["noQuery"] == 1
    assert out["mask"] == 0, "prefetch_i has no data mask"
    assert got["tlbReq_valid"] == 1
    assert got["tlbReq_isPrefetch"] == 1
    assert got["tlbReq_kill"] == 1
    assert got["dcacheReq_valid"] == 0, "prefetch_i must not access the DCache"
    s0.coverage.sample_case("lane.scalar_prefetch_i")
    s0.coverage.sample_case("dcache.prefetch_i_suppressed")
    run(s0, make(ldin=ldin_bits(fu=0x03, src0=0x2000, imm=0x10)), "prefetch_r")


def test_scalar_prefetch_r_still_accesses_the_dcache(s0):
    got = run(s0, make(ldin=ldin_bits(fu=0x03, src0=0x2000, imm=0x20)),
              "prefetch_r")
    out = got["pipeOut_bits"]
    assert out["accessType_instrType"] == 4
    assert out["accessType_pftType"] == 2
    assert out["noQuery"] == 0
    assert out["mask"] == 0
    assert got["tlbReq_isPrefetch"] == 1
    assert got["dcacheReq_valid"] == 1
    assert got["dcacheReq_cmd"] == 0x2
    assert got["dcacheReq_instrtype"] == 3
    s0.coverage.sample_case("lane.scalar_prefetch_r")


# --------------------------------------------------------------- replay order
def test_hi_priority_replay_lane(s0):
    bits = replay_bits(entrance=0x02, vaddr=0x40, uop_pdest=9)
    got = run(s0, make(replay=bits, ldin=ldin_bits()), "hi replay")
    assert got["lane_valid"][1] == 1 and got["lane_valid"][3] == 0
    assert got["pipeOut_bits"]["entrance"] == 0x02
    assert got["replay_ready"] == 1
    s0.coverage.sample_case("order.replay_hi")


def test_lo_priority_replay_only_when_the_replay_is_older(s0):
    older = replay_bits(entrance=0x08, uop_lqIdx_flag=0, uop_lqIdx_value=3)
    younger = replay_bits(entrance=0x08, uop_lqIdx_flag=0, uop_lqIdx_value=9)
    new_load = ldin_bits(lqIdx_flag=0, lqIdx_value=5)
    got = run(s0, make(replay=older, ldin=new_load), "older replay")
    assert got["lane_valid"][3] == 1
    assert got["pipeOut_bits"]["entrance"] == 0x08
    s0.coverage.sample_case("order.replay_lo_when_older")
    got = run(s0, make(replay=younger, ldin=new_load), "younger replay")
    assert got["lane_valid"][3] == 0, "a younger replay must not bypass the new load"
    assert got["pipeOut_valid"] == 1, "the new load still issues"
    assert got["pipeOut_bits"]["entrance"] == 0x40
    assert got["replay_ready"] == 0, "the dropped replay is not consumed"
    s0.coverage.sample_case("order.younger_replay_dropped")


def test_replay_without_a_new_load_is_low_priority(s0):
    bits = replay_bits(entrance=0x08, uop_lqIdx_value=1)
    got = run(s0, make(replay=bits), "replay alone")
    assert got["lane_valid"][3] == 1
    assert got["pipeOut_bits"]["entrance"] == 0x08
    s0.coverage.sample_case("order.replay_without_ldin_is_lo")


def test_ring_order_wraps_with_the_wrap_bit(s0):
    # The new load wrapped (flag=1, value=2 -> absolute 130) while the replaying
    # load did not (flag=0, value=6), so the replay is older even though its
    # plain value is larger.
    replay = replay_bits(entrance=0x08, uop_lqIdx_flag=0, uop_lqIdx_value=6)
    new_load = ldin_bits(lqIdx_flag=1, lqIdx_value=2)
    got = run(s0, make(replay=replay, ldin=new_load), "ring order")
    assert got["lane_valid"][3] == 1
    assert got["pipeOut_bits"]["entrance"] == 0x08


# ------------------------------------------------------------------ arbitration
def test_all_five_lanes_and_the_priority_order(s0):
    inputs = make(unalign=unalign_bits(), replay=replay_bits(entrance=0x02),
                  fast=fast_bits(), ldin=ldin_bits())
    got = run(s0, inputs, "all five")
    assert got["pipeOut_bits"]["entrance"] == 0x01
    assert got["unalignTail_ready"] == 1
    for lane in ("replay", "fast", "ldin"):
        assert got[lane + "_ready" if lane != "fast" else "fastReplay_ready"] == 0
    s0.coverage.sample_case("arb.all_lanes_priority")


def test_backpressure_ready_bitmap_and_the_bubble(s0):
    rng = random.Random(41)
    for mask in range(16):
        inputs = blank_inputs()
        inputs["unalign"]["valid"] = mask & 1
        inputs["unalign"]["bits"] = random_unalign(rng)
        inputs["replay"]["valid"] = (mask >> 1) & 1
        inputs["replay"]["bits"] = replay_bits(entrance=0x02 if (mask >> 2) & 1 else 0x08)
        inputs["fast"]["valid"] = (mask >> 3) & 1
        inputs["fast"]["bits"] = random_fast(rng)
        inputs["ldin"]["valid"] = 1
        inputs["ldin"]["bits"] = random_ldin(rng)
        for ready in (0, 1):
            inputs["dcache_ready"] = ready
            got = run(s0, inputs, f"mask {mask} ready {ready}")
            if ready == 0:
                for lane in ("unalignTail", "replay", "fastReplay", "ldin"):
                    assert got[lane + "_ready"] == 0, (mask, lane)
                assert got["pipeOut_valid"] == 0
            else:
                assert got["unalignTail_ready"] == 1
    s0.coverage.sample_case("arb.backpressure_ready_bitmap")


# -------------------------------------------------------------------- alignment
@pytest.mark.parametrize("fu,size", [(LB, 0), (LH, 1), (LW, 2), (LD, 3), (LD16, 4)])
def test_alignment_decoding_for_every_size(s0, fu, size):
    got = run(s0, make(ldin=ldin_bits(fu=fu, src0=0x3000)), "aligned size")
    assert got["pipeOut_bits"]["align"] == 1, (fu, size)
    if size > 0:
        # First byte offset that violates 2**size alignment (16B for size>=4).
        offset = 1
        got = run(s0, make(ldin=ldin_bits(fu=fu, src0=0x3000 + offset)),
                  "misaligned size")
        assert got["pipeOut_bits"]["align"] == 0, (fu, size)
    s0.coverage.sample_case("align.scalar_each_size")
    s0.coverage.sample_case("align.misaligned_detected")
    # 16B loads additionally require 16B alignment.
    if size >= 4:
        assert is_aligned(4, 0x3000 + 8) is False


def test_prefetch_lane_skips_the_alignment_check(s0):
    # prefetch_i is "misaligned" (size 0 offset 0 is aligned, so use pft mask
    # semantics instead): noAlignCheck comes from instrType[2].
    got = run(s0, make(ldin=ldin_bits(fu=0x01, src0=0x3001)), "prefetch skip")
    assert got["pipeOut_bits"]["align"] == 1
    assert got["pipeOut_bits"]["unalignHead"] == 0
    s0.coverage.sample_case("align.prefetch_skips_check")


def test_unalign_tail_forces_align_low(s0):
    got = run(s0, make(unalign=unalign_bits()), "tail align")
    assert got["pipeOut_bits"]["align"] == 0
    assert got["pipeOut_bits"]["unalignHead"] == 0
    s0.coverage.sample_case("align.tail_forces_unalign")


def test_cross_bank_sets_unalign_head_and_suppresses_wakeup(s0):
    # 8B at 0x300C ends at offset 0x13 -> crosses the 16B word.
    got = run(s0, make(ldin=ldin_bits(fu=LD, src0=0x300C)), "cross bank")
    assert got["pipeOut_bits"]["unalignHead"] == 1
    assert got["pipeOut_valid"] == 1, "the head still issues in this cycle"
    assert got["wakeup_valid"] == 0, "a crossing load is woken up only after the tail"
    s0.coverage.sample_case("crossbank.unalign_head_and_wakeup_suppressed")
    # A non-crossing beat keeps unalignHead low and wakes up normally.
    got = run(s0, make(ldin=ldin_bits(fu=LD, src0=0x3008)), "no cross")
    assert got["pipeOut_bits"]["unalignHead"] == 0


def test_is128_marks_accesses_crossing_the_8b_half_word(s0):
    # 8B at offset 4: starts low, ends in the upper 8B half -> 128-bit request.
    got = run(s0, make(ldin=ldin_bits(fu=LD, src0=0x4004)), "is128 8B")
    assert got["is128Req"] == 1
    # 8B at offset 8: entirely inside the upper half -> single 8B request.
    got = run(s0, make(ldin=ldin_bits(fu=LD, src0=0x4008)), "no is128")
    assert got["is128Req"] == 0
    # tail injection always requests 128 bits.
    got = run(s0, make(unalign=unalign_bits()), "is128 tail")
    assert got["is128Req"] == 1
    s0.coverage.sample_case("is128.crosses_8b_half")
    s0.coverage.sample_case("is128.tail_is_always_128")


# ---------------------------------------------------------------------- TLB
def test_tlb_request_fields_come_from_the_arbitrated_lane(s0):
    ldin = ldin_bits(fu=LD, src0=0x5000, imm=0x10, robIdx_flag=1,
                     robIdx_value=0x33, robIdx_isFormer=1)
    got = run(s0, make(ldin=ldin), "tlb fields")
    assert got["tlbReq_valid"] == 1
    assert got["tlbReq_vaddr"] == 0x5010
    assert got["tlbReq_fullva"] == 0x5010
    assert got["tlbReq_checkfullva"] == 1
    assert got["tlbReq_kill"] == 0
    assert got["tlbReq_no_translate"] == 0
    assert got["tlbReq_robIdx_flag"] == 1
    assert got["tlbReq_robIdx_value"] == 0x33
    assert got["tlbReq_robIdx_isFormer"] == 1
    s0.coverage.sample_case("tlb.request_fields")


def test_fast_replay_does_not_issue_a_tlb_request(s0):
    fast = fast_bits(entrance=0x04, vaddr=0x6000)
    ldin = ldin_bits(fu=LD, src0=0x7000)
    got = run(s0, make(fast=fast, ldin=ldin), "fast tlb")
    # The fast replay wins the arbitration ...
    assert got["pipeOut_bits"]["entrance"] == 0x04
    # ... but it is invisible to the TLB stage; with ldin valid the request is
    # still driven and takes the *ldin* address (the documented fall-through).
    assert got["tlbReq_valid"] == 1
    assert got["tlbReq_vaddr"] == 0x7000
    got = run(s0, make(fast=fast), "fast tlb alone")
    assert got["tlbReq_valid"] == 0, "a lone fast replay never asks for translation"
    s0.coverage.sample_case("tlb.excludes_fast_replay")


def test_checkfullva_is_only_set_on_the_first_issue(s0):
    got = run(s0, make(replay=replay_bits(entrance=0x02, vaddr=0x8000),
                       ldin=ldin_bits(src0=0x9000)), "replay first")
    assert got["tlbReq_checkfullva"] == 0
    got = run(s0, make(ldin=ldin_bits(src0=0x9000)), "ldin first")
    assert got["tlbReq_checkfullva"] == 1
    s0.coverage.sample_case("tlb.checkfullva_only_first_issue")


def test_hyperinst_and_hlvx_are_decoded_from_fuoptype_bits(s0):
    got = run(s0, make(ldin=ldin_bits(fu=0x42)), "hyperinst")
    assert got["tlbReq_hyperinst"] == 1
    assert got["tlbReq_hlvx"] == 0
    got = run(s0, make(ldin=ldin_bits(fu=0x62)), "hlvx")
    assert got["tlbReq_hyperinst"] == 1
    assert got["tlbReq_hlvx"] == 1
    got = run(s0, make(ldin=ldin_bits(fu=0x63)), "hlvx but bit0")
    assert got["tlbReq_hlvx"] == 0, "bit 0 suppresses the HLVX decode"
    s0.coverage.sample_case("tlb.hyperinst_hlvx")


# ------------------------------------------------------------------- DCache
def test_uncache_replay_suppresses_the_dcache_request(s0):
    bits = replay_bits(entrance=0x02, uncacheReplay=1, vaddr=0xA000)
    got = run(s0, make(replay=bits), "uncache replay")
    assert got["pipeOut_valid"] == 1
    assert got["dcacheReq_valid"] == 0
    s0.coverage.sample_case("dcache.uncache_replay_suppressed")


def test_normal_dcache_request_encoding(s0):
    got = run(s0, make(ldin=ldin_bits(fu=LD, src0=0xB000, imm=8,
                                      lqIdx_flag=1, lqIdx_value=0x12)), "dcache")
    assert got["dcacheReq_valid"] == 1
    assert got["dcacheReq_cmd"] == 0
    assert got["dcacheReq_instrtype"] == 0
    assert got["dcacheReq_vaddr"] == 0xB008
    assert got["dcacheReq_vaddr_dup"] == got["dcacheReq_vaddr"]
    assert got["dcacheReq_mask"] == 0xFF00
    assert got["dcacheReq_lqIdx_flag"] == 1
    assert got["dcacheReq_lqIdx_value"] == 0x12
    s0.coverage.sample_case("dcache.normal_request")


# ------------------------------------------------------------------ forwards
def test_sqsb_forward_request_follows_the_arbitration(s0):
    ldin = ldin_bits(fu=LW, src0=0xC000, imm=4, sqIdx_first_flag=1,
                     sqIdx_second_flag=1, sqIdx_value=0x21, loadWaitBit=1,
                     loadWaitStrict=1, waitSqIdx_first_flag=1,
                     waitSqIdx_second_flag=1, waitSqIdx_value=0x33)
    got = run(s0, make(ldin=ldin), "sqsb")
    assert got["sqSbForwardReq_valid"] == 1
    assert got["sqSbForwardReq_vaddr"] == 0xC004
    assert got["sqSbForwardReq_size"] == 2
    assert got["sqSbForwardReq_sqIdx_first_flag"] == 1
    assert got["sqSbForwardReq_sqIdx_second_flag"] == 1
    assert got["sqSbForwardReq_sqIdx_value"] == 0x21
    assert got["sqSbForwardReq_loadWaitBit"] == 1
    assert got["sqSbForwardReq_loadWaitStrict"] == 1
    assert got["sqSbForwardReq_waitSqIdx_first_flag"] == 1
    assert got["sqSbForwardReq_waitSqIdx_second_flag"] == 1
    assert got["sqSbForwardReq_waitSqIdx_value"] == 0x33
    s0.coverage.sample_case("fwd.sqsb_always")


def test_uncache_forward_only_from_the_high_priority_replay(s0):
    hi = replay_bits(entrance=0x02, uncacheReplay=1, vaddr=0xD000,
                     uop_lqIdx_flag=1, uop_lqIdx_value=5)
    got = run(s0, make(replay=hi), "uncache hi")
    assert got["uncacheForwardReq_valid"] == 1
    assert got["uncacheForwardReq_vaddr"] == 0xD000
    assert got["uncacheBypassReq_valid"] == 1
    assert got["uncacheBypassReq_lqIdx_flag"] == 1
    assert got["uncacheBypassReq_lqIdx_value"] == 5
    lo = replay_bits(entrance=0x08, uncacheReplay=1, vaddr=0xD000)
    got = run(s0, make(replay=lo), "uncache lo")
    assert got["uncacheForwardReq_valid"] == 0, "only the hi-priority lane forwards"
    s0.coverage.sample_case("fwd.uncache_only_hi_priority")


def test_mshr_and_tld_forward_on_dchannel_replay(s0):
    bits = replay_bits(entrance=0x02, forwardDChannel=1, mshrId=0xA)
    got = run(s0, make(replay=bits), "dchannel")
    assert got["mshrForwardReq_valid"] == 1
    assert got["mshrForwardReq_mshrId"] == 0xA
    assert got["tldForwardReq_valid"] == 1
    assert got["tldForwardReq_mshrId"] == 0xA
    assert got["uncacheForwardReq_valid"] == 0, "uncache and DChannel are distinct"
    s0.coverage.sample_case("fwd.mshr_tld_forward_dchannel")


def test_uncache_bypass_distinguishes_nc_from_mmio(s0):
    nc = replay_bits(entrance=0x02, uncacheReplay=1, ncReplay=1)
    got = run(s0, make(replay=nc), "nc")
    assert got["uncacheBypassReq_isNCReplay"] == 1
    assert got["uncacheBypassReq_isMMIOReplay"] == 0
    mmio = replay_bits(entrance=0x02, uncacheReplay=1, ncReplay=0)
    got = run(s0, make(replay=mmio), "mmio")
    assert got["uncacheBypassReq_isNCReplay"] == 0
    assert got["uncacheBypassReq_isMMIOReplay"] == 1
    s0.coverage.sample_case("fwd.nc_vs_mmio")


# ------------------------------------------------------------------- wakeup
def test_first_scalar_issue_wakes_up_the_destination(s0):
    got = run(s0, make(ldin=ldin_bits(fu=LD, pdest=0x2A, rfWen=1)), "wakeup")
    assert got["wakeup_valid"] == 1
    assert got["wakeup_pdest"] == 0x2A
    assert got["wakeup_rfWen"] == 1
    assert got["wakeup_fpWen"] == 0
    # Prefetch never wakes a destination.
    got = run(s0, make(ldin=ldin_bits(fu=0x01, pdest=0x2A, rfWen=1)), "pf wakeup")
    assert got["wakeup_valid"] == 0
    s0.coverage.sample_case("wakeup.scalar_issue")


def test_cross_bank_beat_is_not_woken_up(s0):
    got = run(s0, make(ldin=ldin_bits(fu=LD, src0=0x300C, pdest=3, rfWen=1)),
              "wakeup cross")
    assert got["pipeOut_bits"]["unalignHead"] == 1
    assert got["wakeup_valid"] == 0
    # The tail injection *is* the second half and wakes the destination even
    # though its own address is not alignment checked.
    got = run(s0, make(unalign=unalign_bits(uop_pdest=4, uop_rfWen=1)), "tail wake")
    assert got["wakeup_valid"] == 1
    assert got["wakeup_pdest"] == 4
    s0.coverage.sample_case("wakeup.suppressed_by_crossbank")


def test_wakeup_payload_follows_the_winning_lane(s0):
    # unalign tail and replay hi both valid: the tail wins and contributes pdest.
    got = run(s0, make(unalign=unalign_bits(uop_pdest=0x11, uop_fpWen=1),
                       replay=replay_bits(entrance=0x02, uop_pdest=0x22)), "tail pdest")
    assert got["wakeup_pdest"] == 0x11
    assert got["wakeup_fpWen"] == 1
    # fast replay beats the scalar lane when the tail/replay are idle.
    got = run(s0, make(fast=fast_bits(entrance=0x04, accessType_instrType=1,
                                      uop_pdest=0x33, uop_rfWen=1),
                       ldin=ldin_bits(pdest=0x44, rfWen=1)), "fast pdest")
    assert got["wakeup_pdest"] == 0x33
    s0.coverage.sample_case("wakeup.source_priority")


# ------------------------------------------------------------- output register
def test_output_register_holds_when_the_stage_is_empty(s0):
    got = run(s0, make(ldin=ldin_bits(src0=0xE000, pdest=0x5)), "fill")
    assert got["pipeOut_valid"] == 1
    for beat in range(3):
        got = run(s0, blank_inputs(), f"empty {beat}")
        assert got["pipeOut_valid"] == 0
    s0.coverage.sample_case("reg.hold_when_empty")


def test_no_flush_path_a_backpressured_beat_is_simply_lost(s0):
    # There is no flush input and no skid buffer: a beat is only consumed when
    # dcacheReq.ready is high. A stalled cycle must not update the register.
    got = run(s0, make(ldin=ldin_bits(pdest=0x1), ready=0), "stalled")
    assert got["pipeOut_valid"] == 0
    assert got["ldin_ready"] == 0
    assert got["perf1"] == 0, "the stall is counted after two cycles"
    got = run(s0, make(ldin=ldin_bits(pdest=0x2), ready=1), "issue")
    assert got["pipeOut_valid"] == 1
    assert got["pipeOut_bits"]["uop_pdest"] == 0x2
    s0.coverage.sample_case("reg.no_flush_path")


def test_performance_counters_are_two_cycle_delayed(s0):
    # perf1 counts beats lost to dcache backpressure; it is visible one cycle
    # after the stall (one register stage) ...
    run(s0, make(ldin=ldin_bits(), ready=0), "stall")
    got = run(s0, make(ldin=ldin_bits(), ready=1), "issue")
    assert got["perf1"] == 1
    assert got["perf0"] == 0, "perf0 still shows the previous (empty) cycle"
    # ... and perf0 (issued beats) two cycles after the issue.
    got = run(s0, blank_inputs(), "wait 1")
    assert got["perf0"] == 1
    got = run(s0, blank_inputs(), "wait 2")
    assert got["perf0"] == 0
    s0.coverage.sample_case("perf.two_cycle_counters")


# -------------------------------------------------------------------- random
def test_seeded_random_traffic(s0):
    rng = random.Random(20261025)
    for cycle in range(300):
        inputs = blank_inputs()
        inputs["unalign"]["valid"] = 1 if rng.random() < 0.15 else 0
        inputs["unalign"]["bits"] = random_unalign(rng)
        inputs["replay"]["valid"] = 1 if rng.random() < 0.4 else 0
        inputs["replay"]["bits"] = random_replay(rng)
        inputs["fast"]["valid"] = 1 if rng.random() < 0.3 else 0
        inputs["fast"]["bits"] = random_fast(rng)
        inputs["ldin"]["valid"] = 1 if rng.random() < 0.7 else 0
        inputs["ldin"]["bits"] = random_ldin(rng)
        inputs["dcache_ready"] = 1 if rng.random() < 0.75 else 0
        run(s0, inputs, f"random {cycle}")


def test_case_inventory_is_exact():
    assert len(CASES) == len(set(CASES))
    assert len(CASES) == 35
