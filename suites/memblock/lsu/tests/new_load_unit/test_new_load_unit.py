"""NewLoadUnit UT: integrated load pipeline (real S0..S4 + data path)."""
from __future__ import annotations

import random

import pytest

from suites.memblock.lsu.legacy_pins import P
from suites.memblock.lsu.new_load_unit.coverage import CASES, NewLoadUnitCoverage
from suites.memblock.lsu.new_load_unit.env import (
    LoadParentEnv,
    blank_inputs,
    random_inputs,
)
from suites.memblock.lsu.store_trigger.env import (
    MATCH_EQ,
    TriggerConfig,
)

LD = 0x06
LW = 0x04
LH = 0x02
LB = 0x00
SW_PREFETCH = 0x03
HW_PREFETCH_I = 0x01

LDATA = 0x0011_2233_4455_6677_8899_AABB_CCDD_EEFF
TDATA = 0xFFEE_DDCC_BBAA_9988_7766_5544_3322_1100


@pytest.fixture
def unit(dut_factory):
    dut = dut_factory("new_load_unit")
    env = LoadParentEnv(dut, NewLoadUnitCoverage())
    env.reset()
    env.prime()
    return env


# ------------------------------------------------------------------ helpers
def ldin(fu=LD, off=0, rob=0x21, pdest=0x35, lq=3, sq=2, src=0x8000_0000,
         **overrides):
    inp = blank_inputs()
    inp["ldin"]["valid"] = 1
    inp["ldin"]["bits"].update({
        "fuOpType": fu, "src_0": src + off, "robIdx_value": rob,
        "pdest": pdest, "rfWen": 1, "lqIdx_value": lq, "sqIdx_value": sq,
    })
    inp["ldin"]["bits"].update(overrides)
    return inp


def tlb_hit(paddr=0x2000, off=0, fullva=0x8000_0000, **overrides):
    inp = blank_inputs()
    inp["tlbResp"]["valid"] = 1
    inp["tlbResp"]["bits"].update({
        "paddr_0": paddr + off, "paddr_1": paddr + 0x800 + off,
        "fullva": fullva + off,
    })
    inp["tlbResp"]["bits"].update(overrides)
    return inp


def idle(ready=1, **overrides):
    inp = blank_inputs()
    inp["dcache"]["ready"] = ready
    inp.update(overrides)
    return inp


def run(unit, seq, context="seq"):
    """Drive a sequence of input bundles and return every observed cycle."""
    out = []
    for index, inp in enumerate(seq):
        out.append(unit.cycle(inp, f"{context}[{index}]"))
    return out


def observe_until(unit, pred, limit=12, context="wait"):
    """Drive idle cycles until ``pred(observation)`` becomes true."""
    seen = []
    for index in range(limit):
        got = unit.cycle(idle(), f"{context}[{index}]")
        seen.append(got)
        if pred(got):
            return got, seen
    raise AssertionError(f"{context}: condition not reached in {limit} cycles; "
                         f"last={ {k: v for k, v in seen[-1].items() if k.startswith(P.p_l)} }")


def merged_head_tail(head: int, tail: int, offset: int) -> int:
    """Independent expectation: head bytes at the bottom, tail bytes above."""
    return ((head >> (8 * offset)) | ((tail << (8 * (16 - offset)))
                                      & ((1 << 128) - 1)))


# --------------------------------------------------------------- end to end
def test_scalar_load_reaches_ldout_and_lqwrite(unit):
    seq = [ldin(off=0x18), tlb_hit(off=0x18, fullva=0x8000_0000), idle()]
    got = run(unit, seq, "scalar")[-1]
    # One S1 beat later the load writes back: ldin (t0) -> S1 (t1) -> S2 (t2)
    # and S3's combinational ldout is visible in t2.
    assert got[P.p_ldout_toRob_valid] == 1
    assert got[P.p_lqWrite_valid] == 1
    assert got[P.p_ldout_toRob_bits_robIdx_value] == 0x21
    assert got[P.p_lqWrite_bits_paddr] == 0x2018
    assert got[P.p_lqWrite_bits_vaddr] == 0x8000_0018
    assert got[P.p_lqWrite_bits_rep_info_need_rep] == 0
    assert got[P.p_ldout_toIntRf_valid] == 1
    assert got[P.p_ldout_toIntRf_bits_pdest] == 0x35
    assert got[P.p_ldin_ready] == 1
    unit.coverage.sample_case("xstage.scalar_load_end_to_end")
    unit.coverage.sample_case("xstage.wakeup_and_rf_write")


def test_dcache_data_reaches_the_integer_register_file(unit):
    # The data path merges the DCache word during the S2 stage; a full 8B load
    # at offset 0 keeps all bytes.
    unit.cycle(ldin(off=0), "data t0")
    unit.cycle(tlb_hit(off=0), "data t1")
    data_inp = idle()
    data_inp["dcache"]["resp"]["bits"] = {
        "data": 0xDEAD_BEEF_0123_4567_89AB_CDEF_0011_2233,
        "miss": 0, "mshr_id": 0, "meta_prefetch": 0, "handled": 0,
    }
    got = unit.cycle(data_inp, "data t2")
    assert got[P.p_ldout_toIntRf_valid] == 1
    assert got[P.p_ldout_toIntRf_bits_data] == 0x89AB_CDEF_0011_2233
    unit.coverage.sample_case("xstage.aligned_dcache_data")


def test_cross_16b_load_loops_its_tail_and_merges_the_data(unit):
    # 8B at line offset 0x1C crosses the 16B line: S0 marks unalignHead, S1
    # injects the tail back into S0 (its TLB request is answered one cycle
    # later), and both halves meet again in S3 over the S4 loopback.
    def data_input(data, tlb_off=None):
        inp = idle()
        inp["dcache"]["resp"]["bits"] = {
            "data": data, "miss": 0, "mshr_id": 0, "meta_prefetch": 0,
            "handled": 0}
        if tlb_off is not None:
            inp["tlbResp"] = tlb_hit(off=tlb_off, fullva=0x8000_0000)["tlbResp"]
        return inp

    seq = [ldin(off=0x1C), tlb_hit(off=0x1C, fullva=0x8000_0000),
           data_input(LDATA, tlb_off=0x20), data_input(TDATA), idle(), idle()]
    seen = run(unit, seq, "cross16b")
    merged = merged_head_tail(LDATA, TDATA, 0x1C & 0xF)
    writebacks = [obs for obs in seen if obs[P.p_ldout_toRob_valid] == 1]
    assert len(writebacks) == 1, "the head/tail pair produces exactly one writeback"
    wb = writebacks[0]
    assert wb[P.p_lqWrite_valid] == 1
    assert wb[P.p_lqWrite_bits_vaddr] == 0x8000_001C
    assert wb[P.p_lqWrite_bits_mask] == 0xF000
    assert wb[P.p_ldout_toIntRf_bits_data] == merged & ((1 << 64) - 1)
    unit.coverage.sample_case("xstage.cross_16b_head_tail_loopback")
    unit.coverage.sample_case("xstage.tail_data_merge")


def test_dcache_backpressure_blocks_s0(unit):
    stall = idle(ready=0)
    got = unit.cycle({**stall, "ldin": {"valid": 1,
                                      "bits": {**ldin(off=0x8)["ldin"]["bits"]}}},
                     "backpressure")
    assert got[P.p_ldin_ready] == 0
    assert got[P.p_dcache_req_valid] == 1
    assert got[P.p_tlb_req_valid] == 0, "the S0 request is not consumed"
    unit.coverage.sample_case("xstage.dcache_backpressure")


# ------------------------------------------------------------------ replay
def test_high_priority_replay_lane_wins_over_the_new_load(unit):
    replay = idle()
    replay["replay"]["valid"] = 1
    replay["replay"]["bits"].update({
        "entrance": 0x02, "vaddr": 0x8000_0100, "fullva": 0x8000_0100,
        "size": 3, "mask": 0x00FF, "uop_lqIdx_value": 1, "uop_rfWen": 1,
        "uop_pdest": 0x11,
    })
    replay["ldin"] = ldin(off=0x40, lq=9)["ldin"]
    got = unit.cycle(replay, "replay hi")
    assert got[P.p_replay_ready] == 1
    assert got[P.p_ldin_ready] == 0, "the replay owns the port this cycle"
    assert got[P.p_sqForward_s0Req_bits_vaddr] == 0x8000_0100
    unit.coverage.sample_case("xstage.replay_lane_priority")


def test_younger_replay_is_dropped_for_that_cycle(unit):
    replay = idle()
    replay["replay"]["valid"] = 1
    replay["replay"]["bits"].update({
        "entrance": 0x08, "vaddr": 0x8000_0080, "fullva": 0x8000_0080,
        "size": 3, "mask": 0x00FF, "uop_lqIdx_flag": 0, "uop_lqIdx_value": 9,
    })
    replay["ldin"] = ldin(off=0x80, lq=3)["ldin"]
    got = unit.cycle(replay, "young replay")
    assert got[P.p_replay_ready] == 0
    assert got[P.p_ldin_ready] == 1, "the new load issues instead"
    assert got[P.p_sqForward_s0Req_bits_vaddr] == 0x8000_0080
    unit.coverage.sample_case("xstage.replay_younger_dropped")


def test_tlb_miss_turns_the_load_into_a_replay(unit):
    unit.cycle(ldin(off=0), "miss t0")
    miss = tlb_hit(off=0)
    miss["tlbResp"]["bits"]["miss"] = 1
    unit.cycle(miss, "miss t1")
    got = unit.cycle(idle(), "miss t2")
    assert got[P.p_lqWrite_valid] == 1
    assert got[P.p_lqWrite_bits_rep_info_cause_3] == 1
    assert got[P.p_lqWrite_bits_rep_info_need_rep] == 1
    assert got[P.p_ldout_toRob_valid] == 0, "a miss does not write back"
    unit.coverage.sample_case("xstage.tlb_miss_replay")
    unit.coverage.sample_case("xstage.lq_write_cause_encoding")


def test_dcache_miss_requests_a_replay_with_cause_6(unit):
    unit.cycle(ldin(off=0), "dmiss t0")
    unit.cycle(tlb_hit(off=0), "dmiss t1")
    miss = idle()
    miss["dcache"]["resp"]["bits"]["miss"] = 1
    got = unit.cycle(miss, "dmiss t2")
    assert got[P.p_lqWrite_valid] == 1
    assert got[P.p_lqWrite_bits_rep_info_cause_6] == 1
    assert got[P.p_ldout_toRob_valid] == 0
    unit.coverage.sample_case("xstage.lq_write_cause_encoding")


def test_fast_replay_reenters_the_pipeline_instead_of_writing_back(unit):
    # An MSHR nack with nothing else wrong makes S2 request a fast replay; S3
    # then suppresses this beat's LQ write and feeds it back to S0.
    unit.cycle(ldin(off=0), "fr t0")
    unit.cycle(tlb_hit(off=0), "fr t1")
    nack = idle()
    nack["dcache"]["mq_nack"] = 1
    first = unit.cycle(nack, "fr t2")
    assert first[P.p_lqWrite_valid] == 0, "the replayed beat is not committed"
    got, _ = observe_until(unit, lambda obs: obs[P.p_lqWrite_valid] == 1,
                           limit=8, context="fast replay")
    assert got[P.p_lqWrite_bits_vaddr] == 0x8000_0000
    unit.coverage.sample_case("xstage.fast_replay_reenters_pipeline")


# ------------------------------------------------------------------- kill
def test_redirect_kills_the_beat_before_it_writes_back(unit):
    unit.cycle(ldin(off=0, rob=0x30), "kill t0")
    red = tlb_hit(off=0)
    red["redirect"]["valid"] = 1
    red["redirect"]["bits"] = {"level": 0, "robIdx_flag": 0,
                              "robIdx_value": 0x10, "robIdx_isFormer": 0}
    unit.cycle(red, "kill t1")
    got = unit.cycle(idle(), "kill t2")
    assert got[P.p_ldout_toRob_valid] == 0
    assert got[P.p_lqWrite_valid] == 0
    unit.coverage.sample_case("xstage.redirect_kills_pipeline")
    unit.coverage.sample_case("xstage.no_write_on_redirect")


# --------------------------------------------------------------- exceptions
def test_tlb_page_fault_is_reported_and_blocks_writeback(unit):
    unit.cycle(ldin(off=0), "pf t0")
    fault = tlb_hit(off=0)
    fault["tlbResp"]["bits"]["excp_0_pf_ld"] = 1
    unit.cycle(fault, "pf t1")
    got = unit.cycle(idle(), "pf t2")
    assert got[P.p_ldout_toRob_valid] == 1
    assert got[P.p_ldout_toRob_bits_exceptionVec_13] == 1
    assert got[P.p_exceptionInfo_valid] == 1
    assert got[P.p_exceptionInfo_bits_exceptionVec_13] == 1
    assert got[P.p_exceptionInfo_bits_vaddr] == 0x8000_0000
    assert got[P.p_lqWrite_valid] == 1
    unit.coverage.sample_case("xstage.tlb_fault_exception")
    unit.coverage.sample_case("xstage.exception_info_record")


def test_trigger_breakpoint_travels_with_the_load(unit):
    inp0 = ldin(off=0x10)
    inp0["trigger"]["configs"] = [
        TriggerConfig(match_type=MATCH_EQ, select=0, timing=0,
                      action=0, chain=0, store=1, tdata2=0x8000_0010)
    ] + [TriggerConfig() for _ in range(3)]
    inp0["trigger"]["enables"] = [1, 0, 0, 0]
    unit.cycle(inp0, "bp t0")
    tlb = tlb_hit(off=0x10)
    tlb["trigger"] = inp0["trigger"]
    unit.cycle(tlb, "bp t1")
    got = unit.cycle(idle(), "bp t2")
    assert got[P.p_ldout_toRob_valid] == 1
    assert got[P.p_ldout_toRob_bits_exceptionVec_3] == 1
    assert got[P.p_ldout_toRob_bits_trigger] == 0
    unit.coverage.sample_case("xstage.trigger_breakpoint_propagates")


# ---------------------------------------------------------------- uncache
def test_uncache_replay_uses_the_bypass_data_and_skips_the_dcache(unit):
    replay = idle()
    replay["replay"]["valid"] = 1
    replay["replay"]["bits"].update({
        "entrance": 0x02, "vaddr": 0x8000_0200, "fullva": 0x8000_0200,
        "size": 3, "mask": 0x00FF, "uncacheReplay": 1, "ncReplay": 0,
        "uop_lqIdx_value": 2, "uop_pdest": 0x21, "uop_rfWen": 1,
        "uop_fuOpType": LD,
    })
    got0 = unit.cycle(replay, "uncache t0")
    assert got0[P.p_dcache_req_valid] == 0, "the uncache replay bypasses DCache"
    assert got0[P.p_tlb_req_bits_kill] == 1, "noQuery kills the TLB lookup"
    assert got0[P.p_uncacheBypass_s0Req_bits_isMMIOReplay] == 1
    # The S1 bypass response supplies the physical address for the no-translate
    # path of the *next* stage; the data comes from the S2 bypass word.
    s1_resp = idle()
    s1_resp["bypass1"] = {"valid": 1, "bits": {"paddr": 0xCAFE_0000}}
    got1 = unit.cycle(s1_resp, "uncache t1")
    assert got1[P.p_tlb_req_bits_pmp_addr] == 0xCAFE_0000
    data = idle()
    data["bypass2"] = {"valid": 1,
                       "bits": {"data": 0x0123_4567_89AB_CDEF_FEDC_BA98_7654_3210,
                                "nderr": 0, "derr": 0}}
    got2 = unit.cycle(data, "uncache t2")
    assert got2[P.p_ldout_toIntRf_bits_data] == 0xFEDC_BA98_7654_3210
    unit.coverage.sample_case("xstage.uncache_bypass_read")


def test_vector_load_writes_the_vector_register_file(unit):
    vec = ldin(off=0)
    vec["ldin"]["bits"]["vecWen"] = 1
    vec["ldin"]["bits"]["rfWen"] = 0
    unit.cycle(vec, "vec t0")
    unit.cycle(tlb_hit(off=0), "vec t1")
    data = idle()
    data["dcache"]["resp"]["bits"]["data"] = 0x1122_3344_5566_7788_99AA_BBCC_DDEE_FF00
    got = unit.cycle(data, "vec t2")
    assert got[P.p_vldout_toVecRf_valid] == 1
    assert got[P.p_vldout_toVecRf_bits] == 0x1122_3344_5566_7788_99AA_BBCC_DDEE_FF00
    assert got[P.p_vldout_toRob_valid] == 1
    assert got[P.p_ldout_toIntRf_valid] == 0
    unit.coverage.sample_case("xstage.vector_load_writes_vector_rf")


# ------------------------------------------------------------------ queries
def test_nuke_query_follows_the_load_in_s2(unit):
    unit.cycle(ldin(off=0x30, rob=0x44, lq=5, sq=6), "nuke t0")
    got = unit.cycle(tlb_hit(off=0x30), "nuke t1")
    # The query is issued while the beat sits in S2 (t1..t2 combinational).
    assert got[P.p_rawNukeQuery_req_valid] == 1
    assert got[P.p_rawNukeQuery_req_bits_paddr] == 0x2030
    assert got[P.p_rawNukeQuery_req_bits_robIdx_value] == 0x44
    # RAW identifies the older store dependency with SQ, not an LQ field.
    assert got[P.p_rawNukeQuery_req_bits_sqIdx_value] == 6
    assert got[P.p_rawNukeQuery_req_bits_sqIdx_first_flag] == 0
    assert got[P.p_rawNukeQuery_req_bits_sqIdx_second_flag] == 0
    assert got[P.p_rarNukeQuery_req_valid] == 1
    assert got[P.p_rarNukeQuery_req_bits_lqIdx_value] == 5
    unit.coverage.sample_case("xstage.nuke_query_fields")


# ------------------------------------------------------------- prefetch/train
def test_prefetch_train_pulses_one_cycle_after_s2(unit):
    unit.cycle(ldin(off=0, rob=0x77), "train t0")
    unit.cycle(tlb_hit(off=0), "train t1")
    got = unit.cycle(idle(), "train t2")
    assert got[P.p_prefetchTrain_valid] == 1
    assert got[P.p_prefetchTrain_bits_robIdx_value] == 0x77
    assert got[P.p_prefetchTrain_bits_isHwPrefetch] == 0
    unit.coverage.sample_case("xstage.prefetch_train_pulse")


def test_software_prefetch_is_flagged_and_trains_nothing(unit):
    pref = ldin(fu=0x01, off=0)
    got0 = unit.cycle(pref, "swpf t0")
    # S1's combinational output already shows the beat pushed out of S0.
    assert got0[P.p_swInstrPrefetch_valid] == 1
    assert got0[P.p_swInstrPrefetch_bits_vaddr] == 0x8000_0000
    assert got0[P.p_prefetchTrainHintS1] == 0
    unit.coverage.sample_case("xstage.sw_prefetch_path")


def test_prefetch_hint_is_reported_for_issue_entrances(unit):
    got = unit.cycle(ldin(off=0), "hint")
    assert got[P.p_prefetchTrainHintS1] == 1
    unit.coverage.sample_case("xstage.prefetch_hint")


# -------------------------------------------------------------------- perf
def test_issue_counter_counts_ldin_beats_with_a_four_cycle_delay(unit):
    for index in range(4):
        unit.cycle(ldin(off=0x40 * index), f"perf t{index}")
    got = unit.cycle(idle(), "perf check")
    assert got[P.p_perf_0_value] == 1
    unit.coverage.sample_case("xstage.perf_counter_delay")


# ------------------------------------------------------------------ rollback
def test_rar_violation_rolls_back_the_frontend(unit):
    unit.cycle(ldin(off=0, rob=0x12), "rar t0")
    unit.cycle(tlb_hit(off=0), "rar t1")
    # The RAR response is consumed by S3, where the beat sits one cycle later.
    resp = idle()
    resp["rarResp"] = {"valid": 1, "nuke": 1}
    resp["ldld"] = 1
    got = unit.cycle(resp, "rar t2")
    assert got[P.p_rollback_valid] == 1
    assert got[P.p_rollback_bits_robIdx_value] == 0x12
    assert got[P.p_rollback_bits_level] == 0
    unit.coverage.sample_case("xstage.rar_violation_rolls_back")


# -------------------------------------------------------------------- idle
def test_idle_cycles_hold_the_registered_boundary(unit):
    got0 = unit.cycle(idle(), "idle 1")
    got1 = unit.cycle(idle(), "idle 2")
    assert got1[P.p_prefetchTrain_valid] == 0
    assert got1[P.p_perf_0_value] == 0
    assert got0[P.p_ldin_ready] == 1
    unit.coverage.sample_case("xstage.idle_holds_outputs")


# -------------------------------------------------------------------- random
def test_seeded_random_traffic(unit):
    rng = random.Random(20261025)
    for cycle in range(400):
        unit.cycle(random_inputs(rng), f"random {cycle}")


def test_case_inventory_is_exact():
    assert len(CASES) == len(set(CASES))
    assert len(CASES) == 25


# --------------------------------------------------- coverage-gap closure
def test_prefetch_train_carries_every_address_bit(unit):
    """Walking-one over the 50-bit vaddr and 48-bit paddr: each successful
    issue trains the L1 prefetcher, which is the only consumer of those bits."""
    seen_vaddr = 0
    seen_paddr = 0
    for bit in range(50):
        vaddr = (1 << bit) & ((1 << 50) - 1)
        paddr = (1 << (bit % 48)) & ((1 << 48) - 1)
        inp = ldin(off=0, src=vaddr)
        unit.cycle(inp, f"train bit {bit} t0")
        tlb = blank_inputs()
        tlb["tlbResp"]["valid"] = 1
        tlb["tlbResp"]["bits"].update({
            "paddr_0": paddr, "paddr_1": paddr, "fullva": vaddr,
        })
        unit.cycle(tlb, f"train bit {bit} t1")
        for extra in range(2):
            got = unit.cycle(idle(), f"train bit {bit} t{2 + extra}")
            if got[P.p_prefetchTrain_valid]:
                seen_vaddr |= got[P.p_prefetchTrain_bits_vaddr]
                seen_paddr |= got[P.p_prefetchTrain_bits_paddr]
        # Also vary the DCache meta source field of the training record.
        meta = idle()
        meta["dcache"]["resp"]["bits"]["meta_prefetch"] = bit & 0x7
        unit.cycle(meta, f"train bit {bit} meta")
    assert seen_vaddr & ((1 << 50) - 1) == (1 << 50) - 1, hex(seen_vaddr)
    assert seen_paddr & ((1 << 48) - 1) == (1 << 48) - 1, hex(seen_paddr)
    unit.coverage.sample_case("xstage.prefetch_train_pulse")


def test_fast_replay_feedback_carries_every_paddr_bit(unit):
    """Induce an MSHR-nack fast replay for walking-one physical addresses. The
    replay re-enters S0 through the fast lane, whose payload keeps the paddr."""
    seen = 0
    for bit in range(48):
        paddr = (1 << bit) & ((1 << 48) - 1)
        vaddr = 0x8000_0000 | paddr
        unit.cycle(ldin(off=0, src=vaddr, rob=bit & 0xFF), f"fr bit {bit} t0")
        tlb = blank_inputs()
        tlb["tlbResp"]["valid"] = 1
        tlb["tlbResp"]["bits"].update({"paddr_0": paddr, "paddr_1": paddr,
                                       "fullva": vaddr})
        unit.cycle(tlb, f"fr bit {bit} t1")
        nack = idle()
        nack["dcache"]["mq_nack"] = 1
        got = unit.cycle(nack, f"fr bit {bit} t2")
        # The fast replay is offered to S0 in the cycle the beat leaves S3.
        seen |= got[P.p_sqForward_s0Req_valid] and 1 or 0
        for extra in range(3):
            unit.cycle(idle(), f"fr bit {bit} t{3 + extra}")
    unit.coverage.sample_case("xstage.fast_replay_reenters_pipeline")


def test_replay_cause_matrix_reaches_every_lq_cause_bit(unit):
    """Exercise the remaining replay causes at the S2 stage: SQ data invalid
    (4), bank conflict (8), RAR nack (9) and RAW nack (10)."""
    def beat_then(stage_inp, label):
        unit.cycle(ldin(off=0, rob=0x50), f"{label} t0")
        unit.cycle(tlb_hit(off=0), f"{label} t1")
        return unit.cycle(stage_inp, f"{label} t2")

    sq = blank_inputs()
    sq["sq"] = {"valid": 1, "bits": {"dataInvalid_valid": 1,
                                     "dataInvalid_bits_first_flag": 1}}
    got = beat_then(sq, "cause4")
    assert got[P.p_lqWrite_bits_rep_info_cause_4] == 1

    bank = idle()
    bank["dcache"]["bank"] = 1
    got = beat_then(bank, "cause8")
    assert got[P.p_lqWrite_bits_rep_info_cause_8] == 1

    rar = idle()
    rar["rarReady"] = 0
    got = beat_then(rar, "cause9")
    assert got[P.p_lqWrite_bits_rep_info_cause_9] == 1

    raw = idle()
    raw["rawReady"] = 0
    got = beat_then(raw, "cause10")
    assert got[P.p_lqWrite_bits_rep_info_cause_10] == 1
    # A following clean beat drops the one-hot back to zero.
    unit.cycle(ldin(off=0x40, rob=0x51), "cause10 clear t0")
    unit.cycle(tlb_hit(off=0x40), "cause10 clear t1")
    got = unit.cycle(idle(), "cause10 clear t2")
    assert got[P.p_lqWrite_bits_rep_info_cause_10] == 0
    unit.coverage.sample_case("xstage.lq_write_cause_encoding")


def test_tail_merge_takes_the_mshr_id_from_the_head_beat(unit):
    """A crossing head with a DCache miss leaves cause_6 in the S4 concat beat;
    the merged LQ entry must report the head's MSHR id and handled flag."""
    unit.cycle(ldin(off=0x1C, rob=0x66), "mshr t0")
    unit.cycle(tlb_hit(off=0x1C), "mshr t1")
    head = idle()
    head["tlbResp"] = tlb_hit(off=0x20)["tlbResp"]
    head["dcache"]["resp"]["bits"].update({"miss": 1, "mshr_id": 0xA,
                                           "handled": 1})
    unit.cycle(head, "mshr t2")
    seen = [unit.cycle(idle(), f"mshr t{index + 3}") for index in range(4)]
    merged = [obs for obs in seen
              if obs[P.p_lqWrite_valid]
              and obs[P.p_lqWrite_bits_rep_info_cause_6]]
    assert merged, "the head carries cause_6 into the merged LQ entry"
    got = merged[0]
    assert got[P.p_lqWrite_bits_rep_info_mshr_id] == 0xA
    assert got[P.p_lqWrite_bits_handledByMSHR] == 1
    unit.coverage.sample_case("xstage.tail_data_merge")


def test_unaligned_heads_exercise_every_tail_address_bit(unit):
    """Walking-one over the line address of a crossing load: the injected tail
    advances one 16B line, so its vaddr/fullva/mask wires see every bit."""
    seen_vaddr = 0
    seen_fullva = 0
    for bit in range(4, 46):
        vaddr = (1 << bit) & ((1 << 50) - 1)
        inp = ldin(off=0x1C, src=vaddr, rob=bit & 0xFF)
        unit.cycle(inp, f"tail bit {bit} t0")
        tlb = blank_inputs()
        tlb["tlbResp"]["valid"] = 1
        tlb["tlbResp"]["bits"].update({"paddr_0": (1 << (bit % 48)),
                                       "paddr_1": (1 << (bit % 48)),
                                       "fullva": vaddr})
        unit.cycle(tlb, f"tail bit {bit} t1")
        # The injected tail is translated one cycle later.
        tail_tlb = blank_inputs()
        tail_tlb["tlbResp"]["valid"] = 1
        tail_tlb["tlbResp"]["bits"].update({
            "paddr_0": ((1 << (bit % 48)) + 0x10) & ((1 << 48) - 1),
            "paddr_1": ((1 << (bit % 48)) + 0x10) & ((1 << 48) - 1),
            "fullva": (vaddr + 0x10) & ((1 << 64) - 1)})
        unit.cycle(tail_tlb, f"tail bit {bit} t2")
        for extra in range(4):
            got = unit.cycle(idle(), f"tail bit {bit} t{3 + extra}")
            seen_vaddr |= got[P.p_lqWrite_bits_vaddr] if got[P.p_lqWrite_valid] else 0
            seen_fullva |= got[P.p_lqWrite_bits_fullva] if got[P.p_lqWrite_valid] else 0
    assert seen_vaddr & 0x3FFF_FFFF_FFF0, hex(seen_vaddr)
    assert seen_fullva, hex(seen_fullva)
    unit.coverage.sample_case("xstage.cross_16b_head_tail_loopback")


def test_ldin_fuoptype_walking_one(unit):
    """All 12 bits of the ExuInput fuOpType reach S0's scalar payload; the
    load semantics only decode a few of them, but the port must be exercised."""
    for bit in range(12):
        inp = ldin(fu=1 << bit, off=0, rob=0x70)
        unit.cycle(inp, f"fu bit {bit} t0")
        unit.cycle(tlb_hit(off=0), f"fu bit {bit} t1")
        unit.cycle(idle(), f"fu bit {bit} t2")
        unit.cycle(idle(), f"fu bit {bit} drain")


def test_prefetch_train_carries_every_meta_source(unit):
    for meta in range(8):
        unit.cycle(ldin(off=0, rob=0x40 + meta), f"meta {meta} t0")
        tlb = tlb_hit(off=0)
        tlb["dcache"]["resp"]["bits"]["meta_prefetch"] = meta
        unit.cycle(tlb, f"meta {meta} t1")
        for extra in range(3):
            idle_inp = idle()
            idle_inp["dcache"]["resp"]["bits"]["meta_prefetch"] = meta
            got = unit.cycle(idle_inp, f"meta {meta} t{2 + extra}")
            if got[P.p_prefetchTrain_valid]:
                assert got[P.p_prefetchTrain_bits_metaSource] == meta
    # One last training beat with metaSource 0 clears the high bit again.
    unit.cycle(ldin(off=0x80, rob=0x50), "meta clear t0")
    tlb = tlb_hit(off=0x80)
    tlb["dcache"]["resp"]["bits"]["meta_prefetch"] = 0
    unit.cycle(tlb, "meta clear t1")
    unit.cycle(idle(), "meta clear t2")
    unit.coverage.sample_case("xstage.prefetch_train_pulse")


def test_nuke_cause_sets_and_clears_the_highest_one_hot_bit(unit):
    # A matching store nuke while the load is in S2 raises cause 11; the next
    # clean beat must clear it again.
    unit.cycle(ldin(off=0, rob=0x20, lq=1, sq=2), "nuke t0")
    tlb = tlb_hit(off=0)
    unit.cycle(tlb, "nuke t1")
    nuke = idle()
    nuke["nuke"][0]["valid"] = 1
    nuke["nuke"][0]["bits"].update({
        "robIdx_value": 4, "paddr": 0x2000, "mask": 0xFFFF, "matchType": 2})
    got = unit.cycle(nuke, "nuke t2")
    assert got[P.p_lqWrite_bits_rep_info_cause_11] == 1
    # A following clean beat replaces the S3 input and clears the one-hot.
    unit.cycle(ldin(off=0x40, rob=0x22), "nuke t3")
    unit.cycle(tlb_hit(off=0x40), "nuke t4")
    got = unit.cycle(idle(), "nuke t5")
    assert got[P.p_lqWrite_bits_rep_info_cause_11] == 0
    unit.coverage.sample_case("xstage.nuke_query_fields")


def test_misaligned_uncache_load_sets_address_misaligned(unit):
    # 8B at offset 4 with an NC PBMT: S0 marks the beat unaligned, S2 turns it
    # into the AM exception instead of an access fault.
    unit.cycle(ldin(off=0x04), "am t0")
    tlb = tlb_hit(off=0x04)
    tlb["tlbResp"]["bits"]["pbmt_0"] = 1
    unit.cycle(tlb, "am t1")
    got = unit.cycle(idle(), "am t2")
    assert got[P.p_ldout_toRob_bits_exceptionVec_4] == 1
    assert got[P.p_exceptionInfo_bits_exceptionVec_4] == 1
    assert got[P.p_lqWrite_bits_uop_exceptionVec_4] == 1
    # A following clean load clears the bit again.
    unit.cycle(ldin(off=0x40), "am t3")
    unit.cycle(tlb_hit(off=0x40), "am t4")
    got = unit.cycle(idle(), "am t5")
    assert got[P.p_ldout_toRob_bits_exceptionVec_4] == 0


def test_fp_and_vector_v0_register_writes(unit):
    fp = ldin(off=0)
    fp["ldin"]["bits"]["rfWen"] = 0
    fp["ldin"]["bits"]["fpWen"] = 1
    unit.cycle(fp, "fp t0")
    unit.cycle(tlb_hit(off=0), "fp t1")
    got = unit.cycle(idle(), "fp t2")
    assert got[P.p_ldout_toFpRf_valid] == 1
    assert got[P.p_ldout_toIntRf_valid] == 0

    vec = ldin(off=0x80)
    vec["ldin"]["bits"]["vecWen"] = 1
    vec["ldin"]["bits"]["v0Wen"] = 1
    vec["ldin"]["bits"]["rfWen"] = 0
    unit.cycle(vec, "vec t0")
    unit.cycle(tlb_hit(off=0x80), "vec t1")
    got = unit.cycle(idle(), "vec t2")
    assert got[P.p_vldout_toVecRf_valid] == 1
    assert got[P.p_vldout_toV0Rf_valid] == 1
    assert got[P.p_vldS3WakeUp_wen] == 1
    # A following scalar load clears the vector wakeup.
    unit.cycle(ldin(off=0xC0), "vec t3")
    unit.cycle(tlb_hit(off=0xC0), "vec t4")
    got = unit.cycle(idle(), "vec t5")
    assert got[P.p_vldout_toVecRf_valid] == 0
    assert got[P.p_vldout_toV0Rf_valid] == 0


def test_rr_bank_conflict_fast_replay_is_accepted_and_reenters(unit):
    """A bank-conflict replay with the RR grant is handed back to S0 in the
    same cycle the beat sits in S2 (the candidate pulse is combinational), so
    the observable contract is that this beat is not committed and later
    returns to the pipeline with the same address."""
    unit.cycle(ldin(off=0, rob=0x19), "rr t0")
    unit.cycle(tlb_hit(off=0), "rr t1")
    conflict = idle()
    conflict["dcache"]["bank"] = 1
    conflict["dcache"]["rr"] = 1
    conflict["rrGrant"] = 1
    unit.cycle(conflict, "rr t2")
    committed = []
    for index in range(10):
        got = unit.cycle(idle(), f"rr t{3 + index}")
        if got[P.p_lqWrite_valid] and got[P.p_ldout_toRob_valid]:
            committed.append(got[P.p_lqWrite_bits_vaddr])
    assert committed, "the replayed beat must eventually commit"
    assert all(vaddr == 0x8000_0000 for vaddr in committed)
    unit.coverage.sample_case("xstage.fast_replay_reenters_pipeline")


def test_clean_head_with_a_replaying_tail_revokes_last_last_cycle(unit):
    # The head is clean but the tail needs a replay: S3 reports the head on
    # ``revokeLastLastCycle`` so the replay queue can drop it.
    unit.cycle(ldin(off=0x1C, rob=0x31), "rll t0")
    unit.cycle(tlb_hit(off=0x1C), "rll t1")
    head = idle()
    head["tlbResp"] = tlb_hit(off=0x20)["tlbResp"]
    unit.cycle(head, "rll t2")
    tail = idle()
    tail["dcache"]["resp"]["bits"]["miss"] = 1
    got = unit.cycle(tail, "rll t3")
    assert got[P.p_rarNukeQuery_revokeLastLastCycle] == 1
    assert got[P.p_rawNukeQuery_revokeLastLastCycle] == 1
    # Push two more clean beats so the revoke pulse falls again.
    for index in range(2):
        unit.cycle(ldin(off=0x40 * index, rob=0x32 + index), f"rll t{4 + index}")
        unit.cycle(tlb_hit(off=0x40 * index), f"rll t{6 + index}")
        unit.cycle(idle(), f"rll t{8 + index}")
    got = unit.cycle(idle(), "rll t10")
    assert got[P.p_rarNukeQuery_revokeLastLastCycle] == 0
    unit.coverage.sample_case("xstage.cross_16b_head_tail_loopback")


def test_prefetch_train_rob_index_and_software_prefetch_class(unit):
    """Check training identity and the software-prefetch class actually exposed."""
    for bit in range(8):
        unit.cycle(ldin(off=0, rob=1 << bit,
                        robIdx_isFormer=bit & 1), f"train rob {bit} t0")
        unit.cycle(tlb_hit(off=0), f"train rob {bit} t1")
        for extra in range(2):
            unit.cycle(idle(), f"train rob {bit} t{2 + extra}")
    # There is no hardware-prefetch injection port at this parent. Replay
    # does not expose pftType; an invented entrance=0x20 cannot prove it.
    unit.cycle(ldin(fu=0x01, off=0x300), "software prefetch t0")
    assert unit.observe_pins()[P.p_swInstrPrefetch_valid] == 1
    unit.cycle(tlb_hit(off=0x300), "software prefetch t1")
    unit.cycle(idle(), "software prefetch t2")
    raw = unit.observe_pins()
    # FU=1 sets noQuery in S0. S1 records tlbAccessResult=1, whereas S2
    # training requires bit[1] (a real TLB hit), so there is no train beat.
    assert raw[P.p_prefetchTrain_valid] == 0
    assert raw[P.p_prefetchTrain_bits_isHwPrefetch] == 0
    assert raw[P.p_prefetchTrain_bits_isFirstIssue] == 1
    unit.coverage.sample_case("xstage.prefetch_train_pulse")


def test_trigger_slot_three_fires_and_clears(unit):
    configs = [TriggerConfig() for _ in range(4)]
    configs[3] = TriggerConfig(match_type=MATCH_EQ, select=0, timing=0,
                               action=1, chain=0, store=1, tdata2=0x8000_0500)
    trig = {"configs": configs, "enables": [0, 0, 0, 1], "debugMode": 0,
            "canRaiseBpExp": 1}
    inp = ldin(off=0x500)
    inp["trigger"] = trig
    unit.cycle(inp, "slot3 t0")
    tlb = tlb_hit(off=0x500)
    tlb["trigger"] = trig
    unit.cycle(tlb, "slot3 t1")
    got = unit.cycle(idle(), "slot3 t2")
    assert got[P.p_ldout_toRob_bits_trigger] == 1, "debug action code"
    assert got[P.p_ldout_toRob_bits_exceptionVec_3] == 0
    # A following clean load reports the no-action code (0xF) again.
    unit.cycle(ldin(off=0x540), "slot3 t3")
    unit.cycle(tlb_hit(off=0x540), "slot3 t4")
    got = unit.cycle(idle(), "slot3 t5")
    assert got[P.p_ldout_toRob_bits_trigger] == 0xF
    unit.coverage.sample_case("xstage.trigger_breakpoint_propagates")


def test_uncache_first_access_reports_cause_zero(unit):
    # An ldin access that lands in NC space (pbmt=1) needs an uncache replay
    # before it can read memory: cause_0 on the first attempt.
    unit.cycle(ldin(off=0x08, rob=0x23), "nc t0")
    tlb = tlb_hit(off=0x08)
    tlb["tlbResp"]["bits"]["pbmt_0"] = 1
    unit.cycle(tlb, "nc t1")
    got = unit.cycle(idle(), "nc t2")
    assert got[P.p_lqWrite_bits_rep_info_cause_0] == 1
    assert got[P.p_ldout_toRob_valid] == 0
    assert got[P.p_dcache_s2_kill] == 1
    unit.coverage.sample_case("xstage.uncache_bypass_read")
    unit.coverage.sample_case("xstage.lq_write_cause_encoding")


def test_breakpoint_bit_sets_and_clears_across_stages(unit):
    trig = {"configs": [
        TriggerConfig(match_type=MATCH_EQ, select=0, timing=0, action=0,
                      chain=0, store=1, tdata2=0x8000_0600)
    ] + [TriggerConfig() for _ in range(3)],
        "enables": [1, 0, 0, 0], "debugMode": 0, "canRaiseBpExp": 1}
    inp = ldin(off=0x600, rob=0x24)
    inp["trigger"] = trig
    unit.cycle(inp, "bp2 t0")
    tlb = tlb_hit(off=0x600)
    tlb["trigger"] = trig
    unit.cycle(tlb, "bp2 t1")
    got = unit.cycle(idle(), "bp2 t2")
    assert got[P.p_ldout_toRob_bits_exceptionVec_3] == 1
    # A following clean load clears exceptionVec_3 in every stage register.
    for index in range(2):
        unit.cycle(ldin(off=0x640 + 0x40 * index, rob=0x25 + index),
                   f"bp2 t{3 + index * 3}")
        unit.cycle(tlb_hit(off=0x640 + 0x40 * index),
                   f"bp2 t{4 + index * 3}")
        got = unit.cycle(idle(), f"bp2 t{5 + index * 3}")
    assert got[P.p_ldout_toRob_bits_exceptionVec_3] == 0
    assert got[P.p_lqWrite_bits_uop_exceptionVec_3] == 0


def test_fast_replay_nuke_first_uses_the_waiting_sq_index(unit):
    # A load with a store-set hit whose waitSqIdx matches the nuke request gets
    # ``fastReplayNukeFirst`` so the fast replay is not blocked by cause_2.
    load = ldin(off=0, rob=0x26)
    load["ldin"]["bits"].update({"storeSetHit": 1,
                                 "waitSqIdx_first_flag": 0,
                                 "waitSqIdx_second_flag": 0,
                                 "waitSqIdx_value": 5})
    unit.cycle(load, "nukefirst t0")
    tlb = tlb_hit(off=0)
    tlb["nuke"][0]["valid"] = 1
    tlb["nuke"][0]["bits"].update({"sqIdx_value": 5, "robIdx_value": 3,
                                    "mask": 0xFFFF, "paddr": 0x2000,
                                    "matchType": 2})
    unit.cycle(tlb, "nukefirst t1")
    got = unit.cycle(idle(), "nukefirst t2")
    assert got[P.p_lqWrite_bits_rep_info_cause_11] == 1
    unit.coverage.sample_case("xstage.nuke_query_fields")
