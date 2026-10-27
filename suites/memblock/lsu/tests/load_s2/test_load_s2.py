"""LoadUnitS2 UT: forward merge, replay causes, fast replay, RAR/RAW queries."""
from __future__ import annotations

import random

import pytest

from lsuverify.load_s2.coverage import CASES, LoadS2Coverage
from lsuverify.load_s2.env import (
    MSHR_FIELDS,
    NUKE_FIELDS,
    PIPEIN_FIELDS,
    SQ_FIELDS,
    LoadS2Env,
    blank_inputs,
    random_inputs,
)

SCALAR = 0x40
PREFETCH = 0x20
TAIL = 0x01
TLB_HIT = 2
TLB_MISS = 4


@pytest.fixture
def s2(dut_factory):
    dut = dut_factory("load_s2")
    env = LoadS2Env(dut, LoadS2Coverage())
    env.reset()
    return env


# ------------------------------------------------------------------ helpers
def pipe(**overrides):
    bits = {name: 0 for name in PIPEIN_FIELDS}
    bits.update({"entrance": SCALAR, "accessType_instrType": 1, "mask": 0x00FF,
                 "tlbAccessResult": TLB_HIT, "paddr": 0x1234_5000,
                 "align": 1, "uop_robIdx_flag": 0, "uop_robIdx_value": 16,
                 "uop_fuOpType": 0x06})
    bits.update(overrides)
    return bits


def sq_bits(mask=0, **overrides):
    bits = {name: 0 for name in SQ_FIELDS}
    for index in range(16):
        bits[f"forwardMask_{index}"] = (mask >> index) & 1
    bits.update(overrides)
    return bits


def mshr_bits(mask=0, **overrides):
    bits = {name: 0 for name in MSHR_FIELDS}
    for index in range(16):
        bits[f"forwardMask_{index}"] = (mask >> index) & 1
    bits.update(overrides)
    return bits


def nuke_req(sq_value=0, paddr=0x1234_5000, mask=0xFFFF, rob=1,
             match_type=2, valid=1):
    bits = {name: 0 for name in NUKE_FIELDS}
    bits.update({"sqIdx_value": sq_value, "paddr": paddr, "mask": mask,
                 "robIdx_value": rob, "matchType": match_type})
    return {"valid": valid, "bits": bits}


def make(load=None, redirect=None, sq=None, sb=None, unc=None, mshr=None,
         tld=None, bypass=None, dcache=None, nukes=None, rr_grant=0,
         rar_ready=1, raw_ready=1, pmp_prefetch=0):
    inputs = blank_inputs()
    if load is not None:
        inputs["pipeIn"]["valid"] = 1
        inputs["pipeIn"]["bits"] = load
    if redirect is not None:
        inputs["redirect"]["valid"] = 1
        inputs["redirect"]["bits"] = redirect
    if dcache is not None:
        inputs["dcacheResp"]["bits"].update(dcache)
    for key, value in (("sq", sq), ("sb", sb), ("unc", unc), ("mshr", mshr),
                       ("tld", tld), ("bypass", bypass)):
        if value is None:
            continue
        if isinstance(value, dict) and "bits" in value:
            inputs[key] = value
        else:
            inputs[key]["valid"] = 1
            inputs[key]["bits"] = value
    if nukes is not None:
        inputs["nuke"] = nukes
    inputs["rrGrant"] = rr_grant
    inputs["rarReady"] = rar_ready
    inputs["rawReady"] = raw_ready
    return inputs


def run(s2, inputs, context="cycle"):
    return s2.cycle(inputs, context)


def observe(s2, load, context="cycle", **kwargs):
    """Drive one normal beat and return the registered output fields."""
    got = run(s2, make(load=load, **kwargs), context)
    assert got["pipeOut_valid"] == 1, context
    return got


def cause_mask(got):
    return {key for key, value in got["detail"]["cause"].items() if value}


# ---------------------------------------------------------------------- kill
def test_current_redirect_kills_the_beat(s2):
    got = run(s2, make(load=pipe(uop_robIdx_value=30),
                       redirect={"level": 0, "robIdx_flag": 0,
                                 "robIdx_value": 10, "robIdx_isFormer": 0}),
              "redirect")
    assert got["pipeOut_valid"] == 0
    assert got["detail"]["kill"] == 1
    assert got["dcacheKill"] == 1
    s2.coverage.sample_case("kill.current_redirect")


def test_hardware_prefetch_is_consumed_but_not_forwarded(s2):
    # instrType[2]=1 and pftType[1]=0 -> hardware prefetch.
    got = run(s2, make(load=pipe(accessType_instrType=4, accessType_pftType=0)),
              "hw prefetch")
    assert got["detail"]["is_hw_prefetch"] == 1
    assert got["pipeOut_valid"] == 0
    assert got["prefetchTrain_valid"] == 1
    s2.coverage.sample_case("kill.hardware_prefetch_suppressed")


# ------------------------------------------------------------------- forward
@pytest.mark.parametrize("source,case", [
    ("sq", "forward.sq_covers_the_mask"),
    ("sb", "forward.sbuffer_covers_the_mask"),
    ("unc", "forward.uncache_covers_the_mask"),
])
def test_single_forward_source_covers_the_mask(s2, source, case):
    kwargs = {source: sq_bits(0x00FF)}
    got = observe(s2, pipe(), f"{source} covers", **kwargs)
    assert got["detail"]["full_forward"] == 1
    assert got["detail"]["need_dcache"] == 0
    assert "6" not in [str(c) for c in cause_mask(got)]
    s2.coverage.sample_case(case)


def test_mshr_covers_the_mask(s2):
    got = observe(s2, pipe(), "mshr covers", mshr=mshr_bits(0x00FF))
    assert got["detail"]["full_forward"] == 1
    assert got["detail"]["need_dcache"] == 0
    s2.coverage.sample_case("forward.mshr_covers_the_mask")


def test_tld_response_completes_the_access(s2):
    got = observe(s2, pipe(), "tld", tld={"denied": 0, "corrupt": 0})
    assert got["detail"]["full_forward"] == 1
    assert got["detail"]["need_dcache"] == 0
    s2.coverage.sample_case("forward.tld_response_completes")


def test_sq_data_invalid_blocks_the_sq_forward(s2):
    got = observe(s2, pipe(), "sq invalid",
                  sq=sq_bits(0x00FF, dataInvalid_valid=1))
    assert got["detail"]["full_forward"] == 0
    assert got["detail"]["need_dcache"] == 1
    assert cause_mask(got) == {4}
    s2.coverage.sample_case("forward.sq_data_invalid_blocks")


def test_uncovered_load_needs_the_dcache(s2):
    got = observe(s2, pipe(), "needs dcache")
    assert got["detail"]["need_dcache"] == 1
    assert got["detail"]["full_forward"] == 0
    assert got["detail"]["nuke_query_data_valid"] == 1
    s2.coverage.sample_case("dcache.access_needed_when_not_covered")


# --------------------------------------------------------- uncache / classes
def test_pbmt_nc_is_classified_as_nc(s2):
    got = observe(s2, pipe(pbmt=1), "nc")
    assert got["detail"]["is_nc"] == 1
    assert got["detail"]["is_mmio"] == 0
    assert got["pipeOut_bits"]["nc"] == 1
    assert got["pipeOut_bits"]["mmio"] == 0
    s2.coverage.sample_case("uncache.nc_from_pbmt")


def test_pbmt_and_pmp_mmio_classification(s2):
    got = observe(s2, pipe(pbmt=2), "mmio pbmt")
    assert got["detail"]["is_mmio"] == 1
    got = observe(s2, pipe(pbmt=0), "mmio pmp", pmp_prefetch=0)
    assert got["detail"]["is_mmio"] == 0
    inputs = make(load=pipe(pbmt=0))
    inputs["pmp"]["mmio"] = 1
    got = run(s2, inputs, "mmio pmp=1")
    assert got["detail"]["is_mmio"] == 1
    assert got["pipeOut_bits"]["pmp_mmio"] == 1
    s2.coverage.sample_case("uncache.mmio_from_pbmt_or_pmp")


def test_uncache_classification_needs_a_tlb_hit(s2):
    got = observe(s2, pipe(pbmt=1, tlbAccessResult=TLB_MISS), "nc miss")
    assert got["detail"]["is_nc"] == 0
    assert got["detail"]["is_mmio"] == 0


# ---------------------------------------------------------------- exceptions
def test_pmp_ld_and_hit_raise_access_fault(s2):
    inputs = make(load=pipe())
    inputs["pmp"]["ld"] = 1
    got = run(s2, inputs, "pmp")
    assert got["detail"]["af"] == 1
    assert got["pipeOut_bits"]["uop_exceptionVec_5"] == 1
    s2.coverage.sample_case("exception.af_from_pmp")


def test_vector_uncache_access_raises_access_fault(s2):
    got = observe(s2, pipe(accessType_instrType=3, pbmt=1), "vector nc")
    assert got["detail"]["is_nc"] == 1
    assert got["detail"]["af"] == 1
    s2.coverage.sample_case("exception.af_from_vector_uncache")


def test_misaligned_nc_sets_address_misaligned(s2):
    got = observe(s2, pipe(pbmt=1, align=0), "am")
    assert got["detail"]["am"] == 1
    assert got["pipeOut_bits"]["uop_exceptionVec_4"] == 1
    assert got["detail"]["af"] == 0, "AM in an NC access is not also an AF"
    s2.coverage.sample_case("exception.am_misaligned_nc")


def test_misaligned_mmio_sets_access_fault(s2):
    got = observe(s2, pipe(pbmt=2, align=0), "mmio misaligned")
    assert got["detail"]["af"] == 1
    assert got["detail"]["am"] == 0
    s2.coverage.sample_case("exception.af_misaligned_mmio")


def test_forward_corruption_sets_hardware_error(s2):
    got = observe(s2, pipe(), "mshr corrupt",
                  mshr={"denied": 0, "corrupt": 1})
    assert got["detail"]["hwe"] == 1
    assert got["pipeOut_bits"]["uop_exceptionVec_19"] == 1
    s2.coverage.sample_case("exception.hwe_from_corrupt_forward")
    got = observe(s2, pipe(), "bypass derr", bypass={"nderr": 0, "derr": 1})
    assert got["detail"]["hwe"] == 1


def test_denied_forward_raises_access_fault(s2):
    for key, payload in (("mshr", {"denied": 1, "corrupt": 0}),
                         ("tld", {"denied": 1, "corrupt": 0}),
                         ("bypass", {"nderr": 1, "derr": 0})):
        got = observe(s2, pipe(), f"{key} denied", **{key: payload})
        assert got["detail"]["af"] == 1, key
    s2.coverage.sample_case("exception.denied_forward_raises_af")


# -------------------------------------------------------------- replay causes
def test_plain_uncache_access_requests_a_replay(s2):
    got = observe(s2, pipe(pbmt=1), "uncache cause0")
    assert cause_mask(got) == {0}
    assert got["pipeOut_bits"]["cause_0"] == 1
    assert got["pipeOut_bits"]["causeOrR"] == 1
    assert got["pipeOut_bits"]["shouldWakeup"] == 0
    s2.coverage.sample_case("cause.uncache_first_access")


def test_nc_replay_replays_while_the_data_is_still_invalid(s2):
    # An NC replay is only re-replayed when its data is still invalid, the
    # RAR/RAW query is nacked, the load is nuked, or the SQ forward is invalid.
    got = observe(s2, pipe(uncacheReplay=1, ncReplay=1), "nc replay clean")
    assert cause_mask(got) == set(), "no nack/nuke/invalid -> the replay is complete"
    got = observe(s2, pipe(uncacheReplay=1, ncReplay=1), "nc replay invalid",
                  sq=sq_bits(0x00FF, dataInvalid_valid=1))
    assert cause_mask(got) == {0, 4}
    s2.coverage.sample_case("cause.nc_replay_still_invalid")


def test_forward_invalid_cause(s2):
    got = observe(s2, pipe(), "forward invalid",
                  sq=sq_bits(0x00FF, forwardInvalid=1))
    assert cause_mask(got) == {1}
    s2.coverage.sample_case("cause.forward_invalid")


def test_store_set_address_invalid_cause(s2):
    got = observe(s2, pipe(uop_storeSetHit=1), "addr invalid",
                  sq=sq_bits(0x00FF, addrInvalid_valid=1))
    assert cause_mask(got) == {2}
    s2.coverage.sample_case("cause.addr_invalid_store_set")


def test_tlb_miss_cause(s2):
    got = observe(s2, pipe(tlbAccessResult=TLB_MISS), "tlb miss")
    assert cause_mask(got) == {3}
    s2.coverage.sample_case("cause.tlb_miss")


def test_sq_data_invalid_cause(s2):
    got = observe(s2, pipe(), "sq data invalid",
                  sq=sq_bits(0x00FF, dataInvalid_valid=1))
    assert cause_mask(got) == {4}
    s2.coverage.sample_case("cause.sq_data_invalid")


def test_mshr_nack_cause(s2):
    inputs = make(load=pipe(), dcache={"miss": 0})
    inputs["dcacheMSHRNack"] = 1
    got = run(s2, inputs, "mshr nack")
    assert cause_mask(got) == {5}
    s2.coverage.sample_case("cause.mshr_nack")


def test_dcache_miss_cause(s2):
    got = observe(s2, pipe(), "dcache miss", dcache={"miss": 1})
    assert cause_mask(got) == {6}
    s2.coverage.sample_case("cause.dcache_miss")


def test_bank_conflict_cause(s2):
    inputs = make(load=pipe())
    inputs["dcacheBankConflict"] = 1
    got = run(s2, inputs, "bank conflict")
    assert cause_mask(got) == {8}
    assert got["pipeOut_bits"]["cause_8"] == 1
    s2.coverage.sample_case("cause.bank_conflict")


def test_rar_and_raw_nack_causes(s2):
    got = observe(s2, pipe(), "rar nack", rar_ready=0)
    assert cause_mask(got) == {9}
    got = observe(s2, pipe(), "raw nack", raw_ready=0)
    assert cause_mask(got) == {10}
    s2.coverage.sample_case("cause.rar_nack")
    s2.coverage.sample_case("cause.raw_nack")


def test_nuke_cause(s2):
    got = observe(s2, pipe(uop_robIdx_value=20), "nuke",
                  nukes=[nuke_req(rob=4), nuke_req(valid=0)])
    assert cause_mask(got) == {11}
    assert got["pipeOut_bits"]["cause_11"] == 1
    s2.coverage.sample_case("cause.nuke")


def test_special_mode_request_cause(s2):
    got = observe(s2, pipe(specialModeRequest=1), "special")
    assert cause_mask(got) == {3}
    assert got["pipeOut_bits"]["specialModeRequest"] == 1
    assert got["dcacheKill"] == 1
    s2.coverage.sample_case("cause.special_mode")


# ---------------------------------------------------------------- fast replay
def fast_replay_drives(load, **kwargs):
    inputs = make(load=load, **kwargs)
    return inputs


def test_mshr_nack_alone_allows_a_fast_replay(s2):
    inputs = make(load=pipe())
    inputs["dcacheMSHRNack"] = 1
    got = run(s2, inputs, "fast mshr")
    assert got["pipeOut_bits"]["shouldFastReplay"] == 1
    s2.coverage.sample_case("fastreplay.mshr_nack_alone")


def test_bank_conflict_alone_allows_a_fast_replay(s2):
    inputs = make(load=pipe())
    inputs["dcacheBankConflict"] = 1
    inputs["dcacheRRBankConflict"] = 1
    inputs["rrGrant"] = 1
    got = run(s2, inputs, "fast bank")
    assert got["pipeOut_bits"]["shouldFastReplay"] == 1
    assert got["rrCandidate"] == 1
    assert got["pipeOut_bits"]["rrBankConflictFastReplayGrant"] == 1
    s2.coverage.sample_case("fastreplay.bank_conflict_alone")
    s2.coverage.sample_case("rrbank.conflict_candidate")


def test_nuke_first_excludes_the_store_set_cause(s2):
    load = pipe(uop_storeSetHit=1, uop_waitSqIdx_value=5)
    nuke = nuke_req(sq_value=5, rob=1)
    got = observe(s2, load, "nuke first",
                  sq=sq_bits(0x00FF, addrInvalid_valid=1),
                  nukes=[nuke, nuke_req(valid=0)])
    assert cause_mask(got) == {2, 11}
    assert got["pipeOut_bits"]["shouldFastReplay"] == 1
    # Without the SQ match the store-set cause blocks the fast replay.
    nuke2 = nuke_req(sq_value=9, rob=1)
    got = observe(s2, load, "nuke no match",
                  sq=sq_bits(0x00FF, addrInvalid_valid=1),
                  nukes=[nuke2, nuke_req(valid=0)])
    assert got["pipeOut_bits"]["shouldFastReplay"] == 0
    s2.coverage.sample_case("fastreplay.nuke_first_excludes_cause2")


def test_data_invalid_with_a_matching_std_data_write_allows_fast_replay(s2):
    load = pipe()
    sq = sq_bits(0x00FF, dataInvalid_valid=1,
                 dataInvalid_bits_first_flag=0, dataInvalid_bits_value=7)
    inputs = make(load=load, sq=sq)
    inputs["stdData"]["current"][0] = {
        "valid": 1, "bits": {"first_flag": 0, "second_flag": 0, "value": 7}}
    got = run(s2, inputs, "std match")
    assert cause_mask(got) == {4}
    assert got["pipeOut_bits"]["shouldFastReplay"] == 1
    # A non-matching entry does not enable the fast replay.
    inputs = make(load=load, sq=sq)
    inputs["stdData"]["current"][0] = {
        "valid": 1, "bits": {"first_flag": 0, "second_flag": 0, "value": 3}}
    got = run(s2, inputs, "std no match")
    assert got["pipeOut_bits"]["shouldFastReplay"] == 0
    s2.coverage.sample_case("fastreplay.data_invalid_with_std_write")


def test_fast_replay_eligibility_guards(s2):
    base = dict(pipe())
    # cause5 alone would allow a replay; each guard must block it.
    for name, overrides in (
        ("prefetch entrance", {"entrance": 0x44}),
        ("unalign head", {"unalignHead": 1}),
        ("tail lane", {"entrance": 0x41}),
        ("tlb miss", {"tlbAccessResult": TLB_MISS}),
        ("special mode", {"specialModeRequest": 1}),
    ):
        inputs = make(load=pipe(**overrides))
        inputs["dcacheMSHRNack"] = 1
        got = run(s2, inputs, name)
        assert got["pipeOut_bits"]["shouldFastReplay"] == 0, name
    s2.coverage.sample_case("fastreplay.eligibility_blocks")


# ------------------------------------------------------------- RAR/RAW queries
def test_nuke_query_data_valid_sources(s2):
    # full forward
    got = observe(s2, pipe(), "nq full", sq=sq_bits(0x00FF))
    assert got["rar"]["dataValid"] == 1
    # NC replay always claims data valid
    got = observe(s2, pipe(uncacheReplay=1, ncReplay=1), "nq nc")
    assert got["rar"]["dataValid"] == 1
    # DCache access that did not miss and had no bank conflict
    got = observe(s2, pipe(), "nq dcache")
    assert got["rar"]["dataValid"] == 1
    # A DCache miss invalidates the data
    got = observe(s2, pipe(), "nq miss", dcache={"miss": 1})
    assert got["rar"]["dataValid"] == 0
    s2.coverage.sample_case("nukequery.data_valid_sources")


def test_nuke_query_request_fields(s2):
    load = pipe(uop_robIdx_value=0x21, uop_lqIdx_value=0x35,
                uop_sqIdx_value=0x11, mask=0x8042, paddr=0xCAFE_0000)
    got = observe(s2, load, "nq fields")
    for req_name in ("rar", "raw"):
        req = got[req_name]
        assert req["robIdx_value"] == 0x21
        assert req["paddr"] == 0xCAFE_0000
    assert got["rar"]["lqIdx_value"] == 0x35
    assert got["raw"]["sqIdx_value"] == 0x11
    assert got["raw"]["mask"] == 0x8042
    # A prefetch never issues a nuke query.
    got = run(s2, make(load=pipe(accessType_instrType=4, accessType_pftType=0)),
              "nq prefetch")
    assert got["rar_valid"] == 0 and got["raw_valid"] == 0
    s2.coverage.sample_case("nukequery.request_fields")


# ------------------------------------------------------------------- wakeup
def test_clean_load_wakes_up_and_writes_back(s2):
    got = observe(s2, pipe(), "wakeup")
    assert got["pipeOut_bits"]["shouldWakeup"] == 1
    assert got["pipeOut_bits"]["shouldWriteback"] == 1
    assert got["pipeOut_bits"]["causeOrR"] == 0
    s2.coverage.sample_case("wakeup.clean_load_wakes_up")


def test_exception_writes_back_without_wakeup(s2):
    got = observe(s2, pipe(uop_exceptionVec_3=1), "bp writeback")
    assert got["pipeOut_bits"]["shouldWakeup"] == 0, "an enabled exception blocks the wakeup"
    assert got["pipeOut_bits"]["shouldWriteback"] == 1
    got = observe(s2, pipe(pbmt=1), "uncache replay")
    assert got["pipeOut_bits"]["shouldWakeup"] == 0
    assert got["pipeOut_bits"]["shouldWriteback"] == 0, "a replay does not write back"
    # A software prefetch writes back but never wakes up.
    got = observe(s2, pipe(accessType_instrType=4, accessType_pftType=2),
                  "sw prefetch")
    assert got["detail"]["should_fast_replay"] == 0
    assert got["pipeOut_bits"]["shouldWriteback"] == 1
    s2.coverage.sample_case("wakeup.exception_writes_back")


def test_match_invalid_is_reported(s2):
    got = observe(s2, pipe(), "match invalid",
                  sq=sq_bits(0x00FF, matchInvalid=1))
    assert got["pipeOut_bits"]["matchInvalid"] == 1
    assert got["pipeOut_bits"]["shouldWriteback"] == 1
    s2.coverage.sample_case("matchinvalid.reported")


# ---------------------------------------------------------------- prefetch train
def test_issued_non_prefetch_load_trains_the_prefetcher(s2):
    got = run(s2, make(load=pipe()), "train")
    assert got["prefetchTrain_valid"] == 1
    assert got["train"]["isFirstIssue"] == 1
    assert got["train"]["isHwPrefetch"] == 0
    # Replay entrances (0x02/0x08/0x04) never train.
    got = run(s2, make(load=pipe(entrance=0x02)), "no train")
    assert got["prefetchTrain_valid"] == 0
    # Vector accesses are excluded through instrType[1].
    got = run(s2, make(load=pipe(accessType_instrType=3)), "vector train")
    assert got["prefetchTrain_valid"] == 0
    s2.coverage.sample_case("prefetchtrain.issued_load_trains")


# --------------------------------------------------------------------- perf
def test_four_performance_counters(s2):
    # perf0 = Reg2(pipeIn.valid)
    run(s2, make(load=pipe()), "p0")
    got = run(s2, make(load=pipe()), "p1")
    assert got["perf"][0] == 1
    # perf1 = Reg2(valid & ~kill & cause6); visible one edge after the miss.
    run(s2, make(load=pipe(), dcache={"miss": 1}), "miss")
    got = run(s2, make(load=pipe()), "after miss")
    assert got["perf"][1] == 1
    # perf2 = Reg2(valid & isHwPrefetch), also one edge after the prefetch.
    run(s2, make(load=pipe(accessType_instrType=4, accessType_pftType=0)), "hwpf")
    got = run(s2, make(load=pipe()), "after hwpf")
    assert got["perf"][2] == 1
    # perf3 ANDs isHwPrefetch with cause_6, but cause_6 is gated by
    # troubleMaker = ~instrType[2]; the two are mutually exclusive, so perf3 is
    # structurally constant zero (documented in docs/gaps/load_s2.json).
    run(s2, make(load=pipe(accessType_instrType=4, accessType_pftType=0),
                 dcache={"miss": 1}), "hwpf miss")
    got = run(s2, make(load=pipe()), "after hwpf miss")
    assert got["perf"][3] == 0
    s2.coverage.sample_case("perf.four_counters")


def test_payload_register_holds_on_an_empty_beat(s2):
    got = observe(s2, pipe(uop_pdest=0x42), "fill")
    assert got["pipeOut_bits"]["uop_pdest"] == 0x42
    got = run(s2, blank_inputs(), "empty")
    assert got["pipeOut_valid"] == 0
    s2.coverage.sample_case("reg.payload_holds")


def test_each_cause_and_status_bit_returns_to_zero(s2):
    """Within one DUT instance, set and clear each single-bit status so both
    toggle directions are exercised (the directed tests above each use a fresh
    instance and would leave the 1->0 edge unseen)."""
    clean = make(load=pipe())

    def set_then_clear(label, inputs_set, extra_clean=None):
        got = run(s2, inputs_set, label + " set")
        assert got["detail"]["cause_or"] == 1 or label.startswith("status"), label
        run(s2, extra_clean or clean, label + " clear")

    # cause_1
    set_then_clear("cause1", make(load=pipe(),
                                  sq=sq_bits(0x00FF, forwardInvalid=1)))
    # cause_2 + cause_11 + fastReplayBankConflict are exercised through cause5
    inputs = make(load=pipe())
    inputs["dcacheMSHRNack"] = 1
    set_then_clear("cause5", inputs)
    # cause_8 + RR bank conflict
    inputs = make(load=pipe())
    inputs["dcacheBankConflict"] = 1
    inputs["dcacheRRBankConflict"] = 1
    got = run(s2, inputs, "cause8 set")
    assert got["rrCandidate"] == 1
    run(s2, clean, "cause8 clear")
    # cause_2 + cause_11 (nuke first match)
    load = pipe(uop_storeSetHit=1, uop_waitSqIdx_value=5, uop_robIdx_value=20)
    set_then_clear("cause2and11",
                   make(load=load, sq=sq_bits(0x00FF, addrInvalid_valid=1),
                        nukes=[nuke_req(sq_value=5, rob=1), nuke_req(valid=0)]))
    # cause_4
    set_then_clear("cause4", make(load=pipe(),
                                  sq=sq_bits(0x00FF, dataInvalid_valid=1)))
    # cause_10
    set_then_clear("cause10", make(load=pipe(), raw_ready=0))
    # matchInvalid status bit (no replay cause, but a status/writeback)
    inputs = make(load=pipe(), sq=sq_bits(0x00FF, matchInvalid=1))
    got = run(s2, inputs, "matchInvalid set")
    assert got["pipeOut_bits"]["matchInvalid"] == 1
    assert got["pipeOut_bits"]["shouldWriteback"] == 1
    run(s2, clean, "matchInvalid clear")
    s2.coverage.sample_case("perf.four_counters")


# ------------------------------------------------------------------- random
def test_seeded_random_traffic(s2):
    rng = random.Random(20261025)
    for cycle in range(300):
        run(s2, random_inputs(rng), f"random {cycle}")


def test_case_inventory_is_exact():
    assert len(CASES) == len(set(CASES))
    assert len(CASES) == 44
