"""LoadUnitS1 UT: redirect kill, TLB merge, exceptions, tail injection, replay."""
from __future__ import annotations

import random

import pytest

from suites.memblock.lsu.load_s1.coverage import CASES, LoadS1Coverage
from suites.memblock.lsu.load_s1.env import (
    PIPEIN_FIELDS,
    REDIRECT_FIELDS,
    TLB_FIELDS,
    LoadS1Env,
    blank_inputs,
    random_nuke,
    random_pipe_bits,
    random_tlb_bits,
    tail_mask,
)
from suites.memblock.lsu.store_trigger.env import (
    ACTION_BREAKPOINT,
    ACTION_CODE_BREAKPOINT,
    ACTION_CODE_DEBUG,
    MATCH_EQ,
    TriggerConfig,
)

LD = 0x06
SCALAR_ENTRANCE = 0x40


@pytest.fixture
def s1(dut_factory):
    dut = dut_factory("load_s1")
    env = LoadS1Env(dut, LoadS1Coverage())
    env.reset()
    return env


# ------------------------------------------------------------------ helpers
def pipe_bits(**overrides):
    bits = {name: 0 for name in PIPEIN_FIELDS}
    bits.update({"entrance": SCALAR_ENTRANCE, "accessType_instrType": 1,
                 "uop_fuOpType": LD, "vaddr": 0x8000_1000,
                 "fullva": 0x8000_1000, "mask": 0x00FF, "size": 3,
                 "uop_robIdx_flag": 0, "uop_robIdx_value": 16})
    bits.update(overrides)
    return bits


def tlb_bits(**overrides):
    bits = {name: 0 for name in TLB_FIELDS}
    bits.update({"paddr_0": 0x1234_5000, "paddr_1": 0x1234_5800,
                 "fullva": 0x8000_1000, "pbmt_0": 1})
    bits.update(overrides)
    return bits


def redirect_bits(**overrides):
    bits = {name: 0 for name in REDIRECT_FIELDS}
    bits.update(overrides)
    return bits


def make(load=None, redirect=None, tlb=None, bypass=None, special=0,
         tail_ready=1, rob_head=None, nukes=None, trigger=None):
    inputs = blank_inputs()
    if load is not None:
        inputs["pipeIn"]["valid"] = 1
        inputs["pipeIn"]["bits"] = load
    if redirect is not None:
        inputs["redirect"]["valid"] = 1
        inputs["redirect"]["bits"] = redirect
    if tlb is not None:
        inputs["tlbResp"]["valid"] = 1
        inputs["tlbResp"]["bits"] = tlb
    if bypass is not None:
        inputs["bypass"]["valid"] = 1
        inputs["bypass"]["bits"] = {"paddr": bypass}
    inputs["specialMode"] = special
    inputs["unalignTail_ready"] = tail_ready
    if rob_head is not None:
        inputs["robHeadPtr"] = rob_head
    if nukes is not None:
        inputs["nuke"] = nukes
    if trigger is not None:
        inputs["trigger"] = trigger
    return inputs


def trigger_cfg(action=ACTION_CODE_BREAKPOINT, match_type=MATCH_EQ, tdata2=0x8000_1000,
                store=1, select=0, chain=0, timing=0):
    return TriggerConfig(match_type=match_type, select=select, timing=timing,
                         action=action, chain=chain, store=store, tdata2=tdata2)


def trigger_set(configs, enables=None, debug=0, bp_exp=1):
    configs = list(configs) + [TriggerConfig()] * (4 - len(configs))
    enables = list([1, 0, 0, 0] if enables is None else enables)
    enables += [0] * (4 - len(enables))
    return {"configs": configs, "enables": enables,
            "debugMode": debug, "canRaiseBpExp": bp_exp}


def run(s1, inputs, context="cycle"):
    return s1.cycle(inputs, context)


def run_beat(s1, inputs, context="cycle"):
    """Drive a beat and return the post-edge observation."""
    return run(s1, inputs, context)


# --------------------------------------------------------------------- kill
def test_invalid_input_kills_everything(s1):
    got = run(s1, make(tlb=tlb_bits()), "invalid")
    assert got["kill"] == 1
    assert got["tlbReqKill"] == 1
    assert got["dcacheKill"] == 1
    assert got["pipeOut_valid"] == 0
    s1.coverage.sample_case("kill.invalid_input")


def test_current_redirect_kills_a_younger_load(s1):
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=30),
                       redirect=redirect_bits(robIdx_value=10),
                       tlb=tlb_bits()), "younger")
    assert got["kill"] == 1
    assert got["pipeOut_valid"] == 0
    assert got["tlbReqKill"] == 1
    s1.coverage.sample_case("kill.current_redirect_younger")


def test_older_load_survives_the_redirect(s1):
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=5),
                       redirect=redirect_bits(robIdx_value=10),
                       tlb=tlb_bits()), "older")
    assert got["kill"] == 0
    assert got["pipeOut_valid"] == 1
    s1.coverage.sample_case("kill.current_redirect_older_kept")


def test_redirect_level_kills_the_same_rob_entry(s1):
    # level=1 compares the whole ROB entry, so only the isFormer bit remains.
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=7, uop_robIdx_isFormer=1),
                       redirect=redirect_bits(level=1, robIdx_value=7,
                                              robIdx_isFormer=1),
                       tlb=tlb_bits()), "level same")
    assert got["kill"] == 1
    # level=0 with the same entry and same isFormer must not kill.
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=7, uop_robIdx_isFormer=1),
                       redirect=redirect_bits(level=0, robIdx_value=7,
                                              robIdx_isFormer=1),
                       tlb=tlb_bits()), "level off")
    assert got["kill"] == 0
    s1.coverage.sample_case("kill.redirect_level_same_entry")


def test_same_entry_isformer_orders_two_uops(s1):
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=7, uop_robIdx_isFormer=0),
                       redirect=redirect_bits(robIdx_value=7, robIdx_isFormer=1),
                       tlb=tlb_bits()), "former redirect")
    assert got["kill"] == 1, "the former half must not outlive the redirect"
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=7, uop_robIdx_isFormer=1),
                       redirect=redirect_bits(robIdx_value=7, robIdx_isFormer=0),
                       tlb=tlb_bits()), "latter load")
    assert got["kill"] == 0
    s1.coverage.sample_case("kill.same_entry_isformer_order")


def test_redirect_kills_one_cycle_later_through_the_delayed_slot(s1):
    # t: redirect with a younger target; the load arrives at t+1.
    run(s1, make(redirect=redirect_bits(robIdx_value=4), tlb=tlb_bits()), "red")
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=20), tlb=tlb_bits()), "load")
    assert got["pipeOut_valid"] == 0, "the delayed redirect must kill this beat"
    s1.coverage.sample_case("kill.one_cycle_delayed_redirect")


def test_two_cycle_delayed_redirect_only_kills_tail_injections(s1):
    # redirect at t, gap at t+1, load at t+2: by then the redirect sits in the
    # second slot, whose kill is gated by entrance[0] (the unalign-tail lane).
    def setup():
        run(s1, make(redirect=redirect_bits(robIdx_value=4), tlb=tlb_bits()), "red")
        run(s1, make(tlb=tlb_bits()), "gap")

    setup()
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=20,
                                      entrance=SCALAR_ENTRANCE), tlb=tlb_bits()),
              "scalar late")
    assert got["pipeOut_valid"] == 1, "a scalar beat is out of the 2-cycle window"
    setup()
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=20, entrance=0x01),
                       tlb=tlb_bits()), "tail late")
    assert got["pipeOut_valid"] == 0, "a late tail injection is re-killed"
    s1.coverage.sample_case("kill.two_cycle_delayed_redirect_tail_only")


# ---------------------------------------------------------------------- TLB
def test_tlb_hit_merges_paddr_fullva_pbmt(s1):
    got = run(s1, make(load=pipe_bits(noQuery=0), tlb=tlb_bits()), "hit")
    assert got["pipeOut_valid"] == 1
    out = got["pipeOut_bits"]
    assert got["tlbHit"] == 1 and got["tlbMiss"] == 0
    assert out["paddr"] == 0x1234_5000
    assert out["fullva"] == 0x8000_1000
    assert out["pbmt"] == 1
    assert out["tlbAccessResult"] == 2
    assert out["tlbException_vaNeedExt"] == 0
    assert out["gpaddr"] == 0
    assert got["dataPathMeta_bankOffset"] == 0
    s1.coverage.sample_case("tlb.hit_merges_paddr_fullva_pbmt")


def test_tlb_miss_marks_the_access_result_and_kills_the_dcache(s1):
    got = run(s1, make(load=pipe_bits(), tlb=tlb_bits(miss=1)), "miss")
    out = got["pipeOut_bits"]
    assert got["tlbMiss"] == 1 and got["tlbHit"] == 0
    assert out["tlbAccessResult"] == 4
    assert out["pbmt"] == 0
    assert got["dcacheKill"] == 1
    assert got["sqForwardKill"] == 1
    s1.coverage.sample_case("tlb.miss_marks_access_result")
    s1.coverage.sample_case("dcache.kill_on_miss_or_exception")


def test_noquery_uses_the_bypass_or_input_paddr(s1):
    got = run(s1, make(load=pipe_bits(noQuery=1, paddr=0xAAA0), tlb=tlb_bits(),
                       bypass=0xBBBB_0000), "noquery bypass")
    out = got["pipeOut_bits"]
    assert out["tlbAccessResult"] == 1
    assert out["paddr"] == 0xBBBB_0000
    assert got["tlbPAddr"] == 0xBBBB_0000
    assert got["dcachePAddr"] == 0xBBBB_0000
    s1.coverage.sample_case("tlb.noquery_bypass_paddr")
    got = run(s1, make(load=pipe_bits(noQuery=1, paddr=0xAAA0), tlb=tlb_bits()),
              "noquery input")
    assert got["pipeOut_bits"]["paddr"] == 0xAAA0
    s1.coverage.sample_case("tlb.noquery_without_bypass")


def test_dcache_paddr_uses_the_second_tlb_port(s1):
    got = run(s1, make(load=pipe_bits(noQuery=0, paddr=0xAAA0),
                       tlb=tlb_bits()), "port1")
    assert got["dcachePAddr"] == 0x1234_5800
    assert got["storeForwardReq_paddr"] == 0x1234_5000
    # tlbPAddr is the no-translate address, taken from the request itself.
    assert got["tlbPAddr"] == 0xAAA0
    s1.coverage.sample_case("tlb.dcache_uses_second_port")


def test_special_mode_requests_kill_the_tlb_and_dcache(s1):
    got = run(s1, make(load=pipe_bits(uop_robIdx_flag=0, uop_robIdx_value=9),
                       special=1, rob_head={"flag": 0, "value": 3, "isFormer": 0},
                       tlb=tlb_bits()), "special")
    assert got["specialRequest"] == 1
    assert got["tlbReqKill"] == 1
    assert got["dcacheKill"] == 1
    assert got["pipeOut_bits"]["specialModeRequest"] == 1
    # The ROB head itself is not a special-mode request.
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=3), special=1,
                       rob_head={"flag": 0, "value": 3, "isFormer": 0},
                       tlb=tlb_bits()), "head")
    assert got["specialRequest"] == 0
    s1.coverage.sample_case("tlb.special_mode_non_head")
    s1.coverage.sample_case("tlb.request_kill_and_noquery_paddr")


# ---------------------------------------------------------------- exceptions
def test_only_the_hit_path_raises_faults(s1):
    excp = tlb_bits(excp_0_pf_ld=1, excp_0_af_ld=1, excp_0_gpf_ld=1)
    got = run(s1, make(load=pipe_bits(), tlb=excp), "all faults")
    out = got["pipeOut_bits"]
    assert (out["uop_exceptionVec_13"], out["uop_exceptionVec_5"],
            out["uop_exceptionVec_21"]) == (1, 1, 1)
    assert got["tlbException"] == 1
    assert got["dcacheKill"] == 1
    # A miss suppresses the fault bits entirely.
    got = run(s1, make(load=pipe_bits(), tlb=tlb_bits(miss=1, excp_0_pf_ld=1)),
              "miss suppresses")
    assert got["tlbException"] == 0
    assert got["pipeOut_bits"]["uop_exceptionVec_13"] == 0
    s1.coverage.sample_case("exception.pf_af_gpf_only_on_hit")


def test_breakpoint_comes_from_the_trigger_and_does_not_kill_the_dcache(s1):
    trig = trigger_set([trigger_cfg(tdata2=0x8000_1000)])
    got = run(s1, make(load=pipe_bits(vaddr=0x8000_1000), tlb=tlb_bits(),
                       trigger=trig), "bp")
    assert got["action"] == ACTION_BREAKPOINT
    assert got["bp"] == 1
    assert got["pipeOut_bits"]["uop_trigger"] == ACTION_BREAKPOINT
    assert got["pipeOut_bits"]["uop_exceptionVec_3"] == 1
    assert got["dcacheKill"] == 0, "a breakpoint does not cancel the data access"
    s1.coverage.sample_case("exception.breakpoint_from_trigger")


# -------------------------------------------------------------------- trigger
def test_vector_unit_stride_trigger_path(s1):
    # instrType[1] selects the vector mask match; fuOpType[6:5] == 0 keeps it
    # unit-stride. The trigger word is tdata2[3:0] inside the 16B line.
    load = pipe_bits(accessType_instrType=3, uop_fuOpType=LD,
                     vaddr=0x8000_1010, mask=0x0004)
    trig = trigger_set([trigger_cfg(tdata2=0x8000_1012)])
    got = run(s1, make(load=load, tlb=tlb_bits(), trigger=trig), "vector")
    assert got["bp"] == 1
    # A strided vector access (fuOpType[6:5] != 0) falls back to the scalar path.
    load = pipe_bits(accessType_instrType=3, uop_fuOpType=LD | 0x60,
                     vaddr=0x8000_1010, mask=0x0004)
    got = run(s1, make(load=load, tlb=tlb_bits(), trigger=trig), "strided")
    assert got["bp"] == 0
    s1.coverage.sample_case("trigger.vector_unit_stride")


def test_prefetch_never_fires_a_trigger(s1):
    load = pipe_bits(accessType_instrType=4, vaddr=0x8000_1000, mask=0)
    trig = trigger_set([trigger_cfg(tdata2=0x8000_1000)])
    got = run(s1, make(load=load, tlb=tlb_bits(), trigger=trig), "prf")
    assert got["bp"] == 0, "isPrf suppresses the scalar trigger path"
    s1.coverage.sample_case("trigger.prefetch_suppresses_trigger")


def test_debug_action_and_each_trigger_slot_fires(s1):
    """Exercise trigger slots 1..3 (each has its own hit/can-fire logic) and the
    debug action branch, which takes priority over the breakpoint action."""
    for slot in (1, 2, 3):
        configs = [TriggerConfig() for _ in range(4)]
        configs[slot] = trigger_cfg(action=ACTION_CODE_DEBUG, tdata2=0x8000_1000)
        enables = [0, 0, 0, 0]
        enables[slot] = 1
        got = run(s1, make(load=pipe_bits(vaddr=0x8000_1000), tlb=tlb_bits(),
                           trigger=trigger_set(configs, enables=enables)),
                  f"slot {slot} debug")
        assert got["action"] == 1, slot
        assert got["pipeOut_bits"]["uop_trigger"] == 1
        # Disable the slot again so its internal hit/can-fire wires fall back.
        run(s1, make(load=pipe_bits(vaddr=0x8000_1000), tlb=tlb_bits(),
                     trigger=trigger_set(configs, enables=[0, 0, 0, 0])),
            f"slot {slot} off")
    s1.coverage.sample_case("trigger.debug_action_and_slot_chain")


# -------------------------------------------------------------------- forwards
def test_forward_kill_terms_differ_between_sq_and_uncache(s1):
    # tlbMiss kills SQ/Sbuffer forwards but not the uncache forward.
    got = run(s1, make(load=pipe_bits(), tlb=tlb_bits(miss=1)), "miss")
    assert got["sqForwardKill"] == 1
    assert got["sbufferForwardKill"] == 1
    assert got["uncacheForwardKill"] == 0
    # A redirect kill hits every forward path.
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=30),
                       redirect=redirect_bits(robIdx_value=2),
                       tlb=tlb_bits()), "redirect")
    assert got["sqForwardKill"] == 1
    assert got["uncacheForwardKill"] == 1
    s1.coverage.sample_case("forward.sq_sbuffer_kill_vs_uncache_kill")


def test_data_path_metadata(s1):
    got = run(s1, make(load=pipe_bits(uop_fuOpType=0x42, uop_fpWen=1,
                                      uncacheReplay=1, ncReplay=0,
                                      unalignHead=1),
                       tlb=tlb_bits()), "meta")
    assert got["dataPathMeta_valid"] == 1
    assert got["dataPathMeta_bankOffset"] == 0
    assert got["dataPathMeta_fuOpType"] == 0x42
    assert got["dataPathMeta_fpWen"] == 1
    assert got["dataPathMeta_isNCReplay"] == 0
    assert got["dataPathMeta_isMMIOReplay"] == 1
    assert got["dataPathMeta_isUnalignHead"] == 1
    got = run(s1, make(load=pipe_bits(uncacheReplay=1, ncReplay=1),
                       tlb=tlb_bits(paddr_0=0x1234_5007)), "nc meta")
    assert got["dataPathMeta_isNCReplay"] == 1
    assert got["dataPathMeta_isMMIOReplay"] == 0
    s1.coverage.sample_case("datapath.meta_fields")


# ----------------------------------------------------------------------- tail
def test_tail_injection_advances_one_line_and_shifts_the_mask(s1):
    load = pipe_bits(vaddr=0x8000_100C, fullva=0x8000_200C, uop_fuOpType=LD,
                     unalignHead=1)
    got = run(s1, make(load=load, tlb=tlb_bits(), tail_ready=1), "tail")
    assert got["unalignTail_valid"] == 1
    assert got["unalignTail_vaddr"] == 0x8000_1010
    assert got["unalignTail_fullva"] == 0x8000_2010
    assert got["unalignTail_mask"] == 0x000F
    assert tail_mask(LD, 0x8000_100C) == 0x000F
    s1.coverage.sample_case("tail.inject_address_and_mask")


def test_sixteen_byte_mask_uses_the_full_word_base(s1):
    # fuOpType[3]=1 selects the 0xFFFF base; offset 0xF spills 15 bytes.
    assert tail_mask(0x0E, 0x8000_100F) == 0x7FFF
    got = run(s1, make(load=pipe_bits(vaddr=0x8000_100F, uop_fuOpType=0x0E,
                                      unalignHead=1), tlb=tlb_bits()), "tail16")
    assert got["unalignTail_mask"] == 0x7FFF
    s1.coverage.sample_case("tail.sixteen_byte_base_mask")


def test_tail_is_emitted_even_when_the_head_is_killed(s1):
    load = pipe_bits(vaddr=0x8000_100C, unalignHead=1, uop_robIdx_value=30)
    got = run(s1, make(load=load, redirect=redirect_bits(robIdx_value=2),
                       tlb=tlb_bits()), "killed head")
    assert got["pipeOut_valid"] == 0
    assert got["unalignTail_valid"] == 1, "the tail is re-killed through the 2-cycle slot"
    s1.coverage.sample_case("tail.emitted_even_when_killed")


# --------------------------------------------------------------------- replay
def test_should_fast_replay_when_the_tail_cannot_be_accepted(s1):
    load = pipe_bits(unalignHead=1)
    got = run(s1, make(load=load, tlb=tlb_bits(), tail_ready=0), "sfr")
    assert got["pipeOut_bits"]["shouldFastReplay"] == 1
    s1.coverage.sample_case("replay.should_fast_replay")


def test_should_fast_replay_suppressed_by_ready_miss_fault_or_bp(s1):
    load = pipe_bits(unalignHead=1)
    got = run(s1, make(load=load, tlb=tlb_bits(), tail_ready=1), "ready")
    assert got["pipeOut_bits"]["shouldFastReplay"] == 0
    got = run(s1, make(load=load, tlb=tlb_bits(miss=1), tail_ready=0), "miss")
    assert got["pipeOut_bits"]["shouldFastReplay"] == 0
    got = run(s1, make(load=load, tlb=tlb_bits(excp_0_pf_ld=1), tail_ready=0),
              "fault")
    assert got["pipeOut_bits"]["shouldFastReplay"] == 0
    trig = trigger_set([trigger_cfg(tdata2=0x8000_1000)])
    got = run(s1, make(load=load, tlb=tlb_bits(), tail_ready=0, trigger=trig), "bp")
    assert got["pipeOut_bits"]["shouldFastReplay"] == 0
    s1.coverage.sample_case("replay.should_fast_replay_suppressed")


def test_fast_replay_nuke_first_matches_the_waiting_store_queue_entry(s1):
    load = pipe_bits(uop_storeSetHit=1, uop_waitSqIdx_first_flag=1,
                     uop_waitSqIdx_second_flag=0, uop_waitSqIdx_value=5)
    nuke = {"valid": 1, "bits": {name: 0 for name in
                                ("robIdx_flag", "robIdx_value", "robIdx_isFormer",
                                 "sqIdx_first_flag", "sqIdx_second_flag",
                                 "sqIdx_value", "paddr", "mask", "matchType")}}
    nuke["bits"].update({"sqIdx_first_flag": 1, "sqIdx_value": 5})
    got = run(s1, make(load=load, tlb=tlb_bits(), nukes=[nuke, blank_nuke()]),
              "nuke first")
    assert got["pipeOut_bits"]["fastReplayNukeFirst"] == 1
    s1.coverage.sample_case("replay.fast_replay_nuke_first")


def blank_nuke():
    return {"valid": 0, "bits": {name: 0 for name in
                                 ("robIdx_flag", "robIdx_value", "robIdx_isFormer",
                                  "sqIdx_first_flag", "sqIdx_second_flag",
                                  "sqIdx_value", "paddr", "mask", "matchType")}}


def test_cause_11_matches_the_cache_line_and_rob_order(s1):
    nuke = blank_nuke()
    nuke["valid"] = 1
    nuke["bits"].update({"robIdx_value": 4, "paddr": 0x1234_5000, "mask": 0xFFFF,
                         "matchType": 2})
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=20), tlb=tlb_bits(),
                       nukes=[nuke, blank_nuke()]), "line match")
    assert got["pipeOut_bits"]["cause_11"] == 1
    # Same line but an older load: no nuke.
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=1), tlb=tlb_bits(),
                       nukes=[nuke, blank_nuke()]), "older")
    assert got["pipeOut_bits"]["cause_11"] == 0
    s1.coverage.sample_case("replay.cause_11_line_match")


def test_cause_11_vword_match_requires_mask_overlap(s1):
    nuke = blank_nuke()
    nuke["valid"] = 1
    nuke["bits"].update({"robIdx_value": 4, "paddr": 0x1234_5000, "mask": 0x00F0,
                         "matchType": 0})
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=20, mask=0x000F),
                       tlb=tlb_bits(), nukes=[nuke, blank_nuke()]), "no overlap")
    assert got["pipeOut_bits"]["cause_11"] == 0
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=20, mask=0x0030),
                       tlb=tlb_bits(), nukes=[nuke, blank_nuke()]), "overlap")
    assert got["pipeOut_bits"]["cause_11"] == 1
    assert got["pipeOut_bits"]["cause_11"] == 1
    s1.coverage.sample_case("replay.cause_11_vword_match_and_overlap")


def test_cause_11_requires_a_tlb_hit_or_a_noquery_access(s1):
    nuke = blank_nuke()
    nuke["valid"] = 1
    nuke["bits"].update({"robIdx_value": 4, "paddr": 0x1234_5000, "mask": 0xFFFF,
                         "matchType": 2})
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=20), tlb=tlb_bits(miss=1),
                       nukes=[nuke, blank_nuke()]), "miss")
    assert got["pipeOut_bits"]["cause_11"] == 0
    got = run(s1, make(load=pipe_bits(uop_robIdx_value=20, noQuery=1, paddr=0x1234_5000),
                       tlb=tlb_bits(), nukes=[nuke, blank_nuke()]), "noquery")
    assert got["pipeOut_bits"]["cause_11"] == 1
    s1.coverage.sample_case("replay.cause_11_requires_hit_or_noquery")


# ------------------------------------------------------------------- prefetch
def test_prefetch_train_hint_from_issue_entrances_only(s1):
    for entrance in (0x20, 0x40):
        got = run(s1, make(load=pipe_bits(entrance=entrance), tlb=tlb_bits()),
                  "hint")
        assert got["prefetchTrainHint"] == 1, hex(entrance)
    got = run(s1, make(load=pipe_bits(entrance=0x02), tlb=tlb_bits()), "replay")
    assert got["prefetchTrainHint"] == 0
    got = run(s1, make(load=pipe_bits(entrance=0x40, uop_robIdx_value=30),
                       redirect=redirect_bits(robIdx_value=2), tlb=tlb_bits()),
              "killed")
    assert got["prefetchTrainHint"] == 0, "a killed beat trains nothing"
    s1.coverage.sample_case("prefetch.train_hint")


def test_software_prefetch_is_reported_separately(s1):
    load = pipe_bits(accessType_instrType=4, accessType_pftType=3, vaddr=0x9000)
    got = run(s1, make(load=load, tlb=tlb_bits()), "sw prefetch")
    assert got["swInstrPrefetch_valid"] == 1
    assert got["swInstrPrefetch_vaddr"] == 0x9000
    assert got["prefetchTrainHint"] == 0
    # prefetch_r (pftType 2) is not the software prefetch class.
    load = pipe_bits(accessType_instrType=4, accessType_pftType=2)
    got = run(s1, make(load=load, tlb=tlb_bits()), "prefetch r")
    assert got["swInstrPrefetch_valid"] == 0
    s1.coverage.sample_case("prefetch.software_prefetch")


# ------------------------------------------------------------- output register
def test_payload_is_captured_even_on_a_killed_beat(s1):
    run(s1, make(load=pipe_bits(uop_robIdx_value=30, uop_pdest=0x55),
                 redirect=redirect_bits(robIdx_value=2), tlb=tlb_bits()), "killed")
    # The killed beat must not be visible as valid, but the payload register was
    # written; the environment checks the hold value every empty cycle.
    got = run(s1, make(tlb=tlb_bits()), "after")
    assert got["pipeOut_valid"] == 0
    s1.coverage.sample_case("reg.payload_captured_on_kill")


def test_payload_holds_when_the_input_stage_is_empty(s1):
    got = run(s1, make(load=pipe_bits(uop_pdest=0x66), tlb=tlb_bits()), "fill")
    assert got["pipeOut_valid"] == 1
    got = run(s1, make(tlb=tlb_bits()), "empty 1")
    assert got["pipeOut_valid"] == 0
    run(s1, make(tlb=tlb_bits()), "empty 2")
    s1.coverage.sample_case("reg.payload_holds_when_empty")


def test_performance_counters_count_issue_and_tlb_miss(s1):
    run(s1, make(load=pipe_bits(), tlb=tlb_bits(miss=1)), "miss beat")
    got = run(s1, make(load=pipe_bits(), tlb=tlb_bits()), "hit beat")
    assert got["perf1"] == 1, "the miss is visible one cycle later"
    assert got["perf0"] == 1, "the previous issue is visible one cycle later"
    got = run(s1, make(tlb=tlb_bits()), "gap")
    assert got["perf0"] == 1 and got["perf1"] == 0
    got = run(s1, make(tlb=tlb_bits()), "gap 2")
    assert got["perf0"] == 0
    s1.coverage.sample_case("perf.two_cycle_counters")


# ---------------------------------------------------------------------- random
def test_seeded_random_traffic(s1):
    rng = random.Random(20261025)
    for cycle in range(300):
        inputs = blank_inputs()
        inputs["pipeIn"]["valid"] = 1 if rng.random() < 0.75 else 0
        inputs["pipeIn"]["bits"] = random_pipe_bits(rng)
        inputs["redirect"]["valid"] = 1 if rng.random() < 0.15 else 0
        inputs["redirect"]["bits"] = {name: rng.randrange(1 << width)
                                      for name, width in REDIRECT_FIELDS.items()}
        inputs["tlbResp"]["valid"] = 1 if rng.random() < 0.8 else 0
        inputs["tlbResp"]["bits"] = random_tlb_bits(rng)
        inputs["bypass"]["valid"] = 1 if rng.random() < 0.2 else 0
        inputs["bypass"]["bits"] = {"paddr": rng.getrandbits(48)}
        inputs["specialMode"] = 1 if rng.random() < 0.1 else 0
        inputs["robHeadPtr"] = {"flag": rng.randrange(2),
                                "value": rng.randrange(256),
                                "isFormer": rng.randrange(2)}
        inputs["unalignTail_ready"] = 1 if rng.random() < 0.6 else 0
        inputs["nuke"] = [random_nuke(rng), random_nuke(rng)]
        inputs["trigger"]["configs"] = [
            TriggerConfig(match_type=rng.randrange(4), select=rng.randrange(2),
                          timing=rng.randrange(2),
                          action=rng.choice([0, 1, 2, 4, 15]),
                          chain=rng.randrange(2), store=rng.randrange(2),
                          tdata2=rng.getrandbits(64)) for _ in range(4)]
        inputs["trigger"]["enables"] = [rng.randrange(2) for _ in range(4)]
        inputs["trigger"]["debugMode"] = rng.randrange(2)
        inputs["trigger"]["canRaiseBpExp"] = rng.randrange(2)
        run(s1, inputs, f"random {cycle}")


def test_case_inventory_is_exact():
    assert len(CASES) == len(set(CASES))
    assert len(CASES) == 36
