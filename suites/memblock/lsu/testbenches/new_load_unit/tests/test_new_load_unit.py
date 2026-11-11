"""NewLoadUnit UT: integrated load pipeline (real S0..S4 + data path).

Each scenario describes load transactions and per-cycle protocol responses
(:class:`CycleInput`); the environment returns an immutable
:class:`LoadPipelineSnapshot` whose stage fields are checked against the
independent S0..S3/data-path reference on every cycle.  The tests never spell a
generated port or index the reference dictionary.
"""
from __future__ import annotations

import random

import pytest

from suites.memblock.lsu.testbenches.new_load_unit.coverage import CASES
from suites.memblock.lsu.testbenches.new_load_unit.coverage import NewLoadUnitCoverage
from suites.memblock.lsu.testbenches.new_load_unit.env import LoadParentEnv
from suites.memblock.lsu.testbenches.new_load_unit.transactions import CycleInput
from suites.memblock.lsu.testbenches.new_load_unit.transactions import DcacheRead
from suites.memblock.lsu.testbenches.new_load_unit.transactions import LoadIssue
from suites.memblock.lsu.testbenches.new_load_unit.transactions import NukeQuery
from suites.memblock.lsu.testbenches.new_load_unit.transactions import RarResponse
from suites.memblock.lsu.testbenches.new_load_unit.transactions import Redirect
from suites.memblock.lsu.testbenches.new_load_unit.transactions import ReplayCause
from suites.memblock.lsu.testbenches.new_load_unit.transactions import ReplayRequest
from suites.memblock.lsu.testbenches.new_load_unit.transactions import RobTag
from suites.memblock.lsu.testbenches.new_load_unit.transactions import SqTag
from suites.memblock.lsu.testbenches.new_load_unit.transactions import Translation
from suites.memblock.lsu.testbenches.new_load_unit.transactions import TriggerSettings
from suites.memblock.lsu.testbenches.new_load_unit.transactions import TriggerSlot
from suites.memblock.lsu.testbenches.store_trigger.env import MATCH_EQ

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
def issue(fu=LD, off=0, rob=0x21, pdest=0x35, lq=3, sq=2, src=0x8000_0000,
          is_former=0, **options):
    """One load issue transaction with the historical defaults."""
    return LoadIssue(address=src + off, rob=RobTag(value=rob, is_former=is_former),
                     fu_op=fu, pdest=pdest, lq_idx=lq, sq_idx=sq, **options)


def translation(off=0, fullva=0x8000_0000, paddr=0x2000, miss=False, pbmt=0,
                page_fault=False):
    """TLB hit at ``paddr + off`` with the matching virtual address."""
    return Translation.hit(paddr=paddr + off, fullva=fullva + off,
                           miss=miss, pbmt=pbmt, page_fault=page_fault)


def idle(ready=1, **options):
    return CycleInput.idle().with_dcache(ready=bool(ready), **options)


def run(unit, seq, context="seq"):
    """Drive a sequence of transactions and return every observed cycle."""
    out = []
    for index, plan in enumerate(seq):
        out.append(unit.cycle(plan, f"{context}[{index}]"))
    return out


def observe_until(unit, pred, limit=12, context="wait"):
    """Drive idle cycles until ``pred(snapshot)`` becomes true."""
    seen = []
    for index in range(limit):
        got = unit.cycle(idle(), f"{context}[{index}]")
        seen.append(got)
        if pred(got):
            return got, seen
    last = seen[-1]
    raise AssertionError(
        f"{context}: condition not reached in {limit} cycles; "
        f"last lq.valid={last.s3.lq.valid} ldout.valid={last.s3.ldout.valid} "
        f"replay={last.s3.lq.replay_causes.codes()}")


def merged_head_tail(head: int, tail: int, offset: int) -> int:
    """Independent expectation: head bytes at the bottom, tail bytes above."""
    return ((head >> (8 * offset)) | ((tail << (8 * (16 - offset)))
                                      & ((1 << 128) - 1)))


# --------------------------------------------------------------- end to end
def test_scalar_load_reaches_ldout_and_lqwrite(unit):
    load = issue(off=0x18)
    seq = [CycleInput.idle().issue(load),
           CycleInput.idle().translated(translation(off=0x18)),
           idle()]
    got = run(unit, seq, "scalar")[-1]
    # One S1 beat later the load writes back: ldin (t0) -> S1 (t1) -> S2 (t2)
    # and S3's combinational ldout is visible in t2.
    assert got.s3.ldout.valid == 1
    assert got.s3.lq.valid == 1
    assert got.s3.ldout.rob.value == load.rob.value
    assert got.s3.ldout.rob == load.rob
    assert got.s3.lq.uop_rob == load.rob, "LQ write must carry the issued ROB identity"
    assert got.s3.lq.paddr == 0x2018
    assert got.s3.lq.vaddr == 0x8000_0018
    assert got.s3.lq.need_rep == 0
    assert got.s3.int_rf.valid == 1
    assert got.s3.int_rf.pdest == load.pdest
    assert got.s0.ldin_ready == 1
    unit.coverage.sample_case("xstage.scalar_load_end_to_end")
    unit.coverage.sample_case("xstage.wakeup_and_rf_write")


def test_dcache_data_reaches_the_integer_register_file(unit):
    # The data path merges the DCache word during the S2 stage; a full 8B load
    # at offset 0 keeps all bytes.
    unit.cycle(CycleInput.idle().issue(issue(off=0)), "data t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0)), "data t1")
    data_inp = idle().with_dcache_read(DcacheRead(
        data=0xDEAD_BEEF_0123_4567_89AB_CDEF_0011_2233))
    got = unit.cycle(data_inp, "data t2")
    assert got.s3.int_rf.valid == 1
    assert got.s3.int_rf.data == 0x89AB_CDEF_0011_2233
    unit.coverage.sample_case("xstage.aligned_dcache_data")


def test_cross_16b_load_loops_its_tail_and_merges_the_data(unit):
    # 8B at line offset 0x1C crosses the 16B line: S0 marks unalignHead, S1
    # injects the tail back into S0 (its TLB request is answered one cycle
    # later), and both halves meet again in S3 over the S4 loopback.
    def data_input(data, tlb_off=None):
        plan = idle().with_dcache_read(DcacheRead(data=data))
        if tlb_off is not None:
            plan = plan.translated(translation(off=tlb_off))
        return plan

    seq = [CycleInput.idle().issue(issue(off=0x1C)),
           CycleInput.idle().translated(translation(off=0x1C)),
           data_input(LDATA, tlb_off=0x20), data_input(TDATA), idle(), idle()]
    seen = run(unit, seq, "cross16b")
    merged = merged_head_tail(LDATA, TDATA, 0x1C & 0xF)
    writebacks = [obs for obs in seen if obs.s3.ldout.valid == 1]
    assert len(writebacks) == 1, "the head/tail pair produces exactly one writeback"
    wb = writebacks[0]
    assert wb.s3.lq.valid == 1
    assert wb.s3.lq.vaddr == 0x8000_001C
    assert wb.s3.lq.mask == 0xF000
    assert wb.s3.int_rf.data == merged & ((1 << 64) - 1)
    unit.coverage.sample_case("xstage.cross_16b_head_tail_loopback")
    unit.coverage.sample_case("xstage.tail_data_merge")


def test_dcache_backpressure_blocks_s0(unit):
    got = unit.cycle(
        CycleInput.idle().with_dcache(ready=False).issue(issue(off=0x8)),
        "backpressure")
    assert got.s0.ldin_ready == 0
    assert got.s0.dcache.valid == 1
    assert got.s0.tlb.valid == 0, "the S0 request is not consumed"
    unit.coverage.sample_case("xstage.dcache_backpressure")


# ------------------------------------------------------------------ replay
def test_high_priority_replay_lane_wins_over_the_new_load(unit):
    replay = ReplayRequest(vaddr=0x8000_0100, fullva=0x8000_0100,
                           entrance=0x02, size=3, mask=0x00FF, lq_idx=1,
                           pdest=0x11, rf_wen=True)
    got = unit.cycle(CycleInput.idle().replaying(replay).issue(issue(off=0x40, lq=9)),
                     "replay hi")
    assert got.s0.replay_ready == 1
    assert got.s0.ldin_ready == 0, "the replay owns the port this cycle"
    assert got.s0.store_forward.vaddr == 0x8000_0100
    unit.coverage.sample_case("xstage.replay_lane_priority")


def test_younger_replay_is_dropped_for_that_cycle(unit):
    replay = ReplayRequest(vaddr=0x8000_0080, fullva=0x8000_0080,
                           entrance=0x08, size=3, mask=0x00FF, lq_idx=9)
    got = unit.cycle(CycleInput.idle().replaying(replay).issue(issue(off=0x80, lq=3)),
                     "young replay")
    assert got.s0.replay_ready == 0
    assert got.s0.ldin_ready == 1, "the new load issues instead"
    assert got.s0.store_forward.vaddr == 0x8000_0080
    unit.coverage.sample_case("xstage.replay_younger_dropped")


def test_tlb_miss_turns_the_load_into_a_replay(unit):
    unit.cycle(CycleInput.idle().issue(issue(off=0)), "miss t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0, miss=True)),
               "miss t1")
    got = unit.cycle(idle(), "miss t2")
    assert got.s3.lq.valid == 1
    assert got.s3.lq.replay_cause(ReplayCause.TLB_MISS)
    assert got.s3.lq.need_rep == 1
    assert got.s3.ldout.valid == 0, "a miss does not write back"
    unit.coverage.sample_case("xstage.tlb_miss_replay")
    unit.coverage.sample_case("xstage.lq_write_cause_encoding")


def test_dcache_miss_requests_a_replay_with_cause_6(unit):
    unit.cycle(CycleInput.idle().issue(issue(off=0)), "dmiss t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0)), "dmiss t1")
    miss = idle().with_dcache_read(DcacheRead(miss=True))
    got = unit.cycle(miss, "dmiss t2")
    assert got.s3.lq.valid == 1
    assert got.s3.lq.replay_cause(ReplayCause.DCACHE_MISS)
    assert got.s3.ldout.valid == 0
    unit.coverage.sample_case("xstage.lq_write_cause_encoding")


def test_fast_replay_reenters_the_pipeline_instead_of_writing_back(unit):
    # An MSHR nack with nothing else wrong makes S2 request a fast replay; S3
    # then suppresses this beat's LQ write and feeds it back to S0.
    unit.cycle(CycleInput.idle().issue(issue(off=0)), "fr t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0)), "fr t1")
    nack = idle().with_dcache(mshr_nack=True)
    first = unit.cycle(nack, "fr t2")
    assert first.s3.lq.valid == 0, "the replayed beat is not committed"
    got, _ = observe_until(unit, lambda obs: obs.s3.lq.valid == 1,
                           limit=8, context="fast replay")
    assert got.s3.lq.vaddr == 0x8000_0000
    unit.coverage.sample_case("xstage.fast_replay_reenters_pipeline")


# ------------------------------------------------------------------- kill
def test_redirect_kills_the_beat_before_it_writes_back(unit):
    unit.cycle(CycleInput.idle().issue(issue(off=0, rob=0x30)), "kill t0")
    red = CycleInput.idle().translated(translation(off=0)).redirecting(
        Redirect(valid=True, rob=RobTag(value=0x10), level=0))
    unit.cycle(red, "kill t1")
    got = unit.cycle(idle(), "kill t2")
    assert got.s3.ldout.valid == 0
    assert got.s3.lq.valid == 0
    unit.coverage.sample_case("xstage.redirect_kills_pipeline")
    unit.coverage.sample_case("xstage.no_write_on_redirect")


# --------------------------------------------------------------- exceptions
def test_tlb_page_fault_is_reported_and_blocks_writeback(unit):
    unit.cycle(CycleInput.idle().issue(issue(off=0)), "pf t0")
    unit.cycle(CycleInput.idle().translated(
        translation(off=0, page_fault=True)), "pf t1")
    got = unit.cycle(idle(), "pf t2")
    assert got.s3.ldout.valid == 1
    assert got.s3.ldout.exceptions.load_page_fault
    assert got.s3.exception_info.valid == 1
    assert got.s3.exception_info.exceptions.load_page_fault
    assert got.s3.exception_info.vaddr == 0x8000_0000
    assert got.s3.lq.valid == 1
    unit.coverage.sample_case("xstage.tlb_fault_exception")
    unit.coverage.sample_case("xstage.exception_info_record")


def test_trigger_breakpoint_travels_with_the_load(unit):
    trigger = TriggerSettings(
        configs=[TriggerSlot(match_type=MATCH_EQ, select=0, timing=0,
                               action=0, chain=0, store=1,
                               tdata2=0x8000_0010)]
                + [TriggerSlot() for _ in range(3)],
        enables=[True, False, False, False])
    inp0 = CycleInput.idle().issue(issue(off=0x10)).with_trigger(trigger)
    unit.cycle(inp0, "bp t0")
    tlb = CycleInput.idle().translated(translation(off=0x10)).with_trigger(trigger)
    unit.cycle(tlb, "bp t1")
    got = unit.cycle(idle(), "bp t2")
    assert got.s3.ldout.valid == 1
    assert got.s3.ldout.exceptions.breakpoint
    assert got.s3.ldout.trigger == 0
    unit.coverage.sample_case("xstage.trigger_breakpoint_propagates")


# ---------------------------------------------------------------- uncache
def test_uncache_replay_uses_the_bypass_data_and_skips_the_dcache(unit):
    replay = ReplayRequest(vaddr=0x8000_0200, fullva=0x8000_0200,
                           entrance=0x02, size=3, mask=0x00FF, lq_idx=2,
                           pdest=0x21, rf_wen=True, fu_op=LD,
                           uncache_replay=True, nc_replay=False)
    got0 = unit.cycle(CycleInput.idle().replaying(replay), "uncache t0")
    assert got0.s0.dcache.valid == 0, "the uncache replay bypasses DCache"
    assert got0.s0.tlb.kill == 1, "noQuery kills the TLB lookup"
    assert got0.s0.uncache_bypass.replay_is_mmio == 1
    # The S1 bypass response supplies the physical address for the no-translate
    # path of the *next* stage; the data comes from the S2 bypass word.
    s1_resp = idle().with_bypass1(valid=True, paddr=0xCAFE_0000)
    got1 = unit.cycle(s1_resp, "uncache t1")
    assert got1.s1.tlb_pmp_addr == 0xCAFE_0000
    data = idle().with_bypass2(
        valid=True, data=0x0123_4567_89AB_CDEF_FEDC_BA98_7654_3210,
        nderr=False, derr=False)
    got2 = unit.cycle(data, "uncache t2")
    assert got2.s3.int_rf.data == 0xFEDC_BA98_7654_3210
    unit.coverage.sample_case("xstage.uncache_bypass_read")


def test_vector_load_writes_the_vector_register_file(unit):
    vec = issue(off=0, rf_wen=False, vec_wen=True)
    unit.cycle(CycleInput.idle().issue(vec), "vec t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0)), "vec t1")
    data = idle().with_dcache_read(
        DcacheRead(data=0x1122_3344_5566_7788_99AA_BBCC_DDEE_FF00))
    got = unit.cycle(data, "vec t2")
    assert got.s3.vec_rf.valid == 1
    assert got.s3.vec_rf.data == 0x1122_3344_5566_7788_99AA_BBCC_DDEE_FF00
    assert got.s3.vldout.valid == 1
    assert got.s3.int_rf.valid == 0
    unit.coverage.sample_case("xstage.vector_load_writes_vector_rf")


# ------------------------------------------------------------------ queries
def test_nuke_query_follows_the_load_in_s2(unit):
    unit.cycle(CycleInput.idle().issue(issue(off=0x30, rob=0x44, lq=5, sq=6)),
               "nuke t0")
    got = unit.cycle(CycleInput.idle().translated(translation(off=0x30)),
                     "nuke t1")
    # The query is issued while the beat sits in S2 (t1..t2 combinational).
    assert got.s2.raw_nuke_query.valid == 1
    assert got.s2.raw_nuke_query.paddr == 0x2030
    assert got.s2.raw_nuke_query.rob.value == 0x44
    # RAW identifies the older store dependency with SQ, not an LQ field.
    assert got.s2.raw_nuke_query.sq.value == 6
    assert got.s2.raw_nuke_query.sq.first_flag == 0
    assert got.s2.raw_nuke_query.sq.second_flag == 0
    assert got.s2.rar_nuke_query.valid == 1
    assert got.s2.rar_nuke_query.lq.value == 5
    unit.coverage.sample_case("xstage.nuke_query_fields")


# ------------------------------------------------------------- prefetch/train
def test_prefetch_train_pulses_one_cycle_after_s2(unit):
    unit.cycle(CycleInput.idle().issue(issue(off=0, rob=0x77)), "train t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0)), "train t1")
    got = unit.cycle(idle(), "train t2")
    assert got.prefetch_train.valid == 1
    assert got.prefetch_train.rob.value == 0x77
    assert got.prefetch_train.is_hw_prefetch == 0
    unit.coverage.sample_case("xstage.prefetch_train_pulse")


def test_software_prefetch_is_flagged_and_trains_nothing(unit):
    pref = issue(fu=0x01, off=0)
    got0 = unit.cycle(CycleInput.idle().issue(pref), "swpf t0")
    # S1's combinational output already shows the beat pushed out of S0.
    assert got0.s1.sw_prefetch.valid == 1
    assert got0.s1.sw_prefetch.vaddr == 0x8000_0000
    assert got0.s1.prefetch_train_hint == 0
    unit.coverage.sample_case("xstage.sw_prefetch_path")


def test_prefetch_hint_is_reported_for_issue_entrances(unit):
    got = unit.cycle(CycleInput.idle().issue(issue(off=0)), "hint")
    assert got.s1.prefetch_train_hint == 1
    unit.coverage.sample_case("xstage.prefetch_hint")


# -------------------------------------------------------------------- perf
def test_issue_counter_counts_ldin_beats_with_a_four_cycle_delay(unit):
    for index in range(4):
        unit.cycle(CycleInput.idle().issue(issue(off=0x40 * index)),
                   f"perf t{index}")
    got = unit.cycle(idle(), "perf check")
    assert got.perf.issue_count == 1
    unit.coverage.sample_case("xstage.perf_counter_delay")


# ------------------------------------------------------------------ rollback
def test_rar_violation_rolls_back_the_frontend(unit):
    unit.cycle(CycleInput.idle().issue(issue(off=0, rob=0x12)), "rar t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0)), "rar t1")
    # The RAR response is consumed by S3, where the beat sits one cycle later.
    resp = idle().with_rar(RarResponse(valid=True, nuke=True)).with_ldld_check()
    got = unit.cycle(resp, "rar t2")
    assert got.s3.rollback.valid == 1
    assert got.s3.rollback.rob.value == 0x12
    assert got.s3.rollback.level == 0
    unit.coverage.sample_case("xstage.rar_violation_rolls_back")


# -------------------------------------------------------------------- idle
def test_idle_cycles_hold_the_registered_boundary(unit):
    got0 = unit.cycle(idle(), "idle 1")
    got1 = unit.cycle(idle(), "idle 2")
    assert got1.prefetch_train.valid == 0
    assert got1.perf.issue_count == 0
    assert got0.s0.ldin_ready == 1
    unit.coverage.sample_case("xstage.idle_holds_outputs")


# -------------------------------------------------------------------- random
def test_seeded_random_traffic(unit):
    rng = random.Random(20261025)
    for cycle in range(400):
        unit.random_cycle(rng, f"random {cycle}")


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
        inp = issue(off=0, src=vaddr)
        unit.cycle(CycleInput.idle().issue(inp), f"train bit {bit} t0")
        tlb = Translation(paddr=paddr, paddr_1=paddr, fullva=vaddr)
        unit.cycle(CycleInput.idle().translated(tlb), f"train bit {bit} t1")
        for extra in range(2):
            got = unit.cycle(idle(), f"train bit {bit} t{2 + extra}")
            if got.prefetch_train.valid:
                seen_vaddr |= got.prefetch_train.vaddr
                seen_paddr |= got.prefetch_train.paddr
        # Also vary the DCache meta source field of the training record.
        meta = idle().with_dcache_read(DcacheRead(meta_prefetch=bit & 0x7))
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
        unit.cycle(CycleInput.idle().issue(
            issue(off=0, src=vaddr, rob=bit & 0xFF)), f"fr bit {bit} t0")
        tlb = Translation(paddr=paddr, paddr_1=paddr, fullva=vaddr)
        unit.cycle(CycleInput.idle().translated(tlb), f"fr bit {bit} t1")
        nack = idle().with_dcache(mshr_nack=True)
        got = unit.cycle(nack, f"fr bit {bit} t2")
        # The fast replay is offered to S0 in the cycle the beat leaves S3.
        seen |= got.s0.store_forward.valid and 1 or 0
        for extra in range(3):
            unit.cycle(idle(), f"fr bit {bit} t{3 + extra}")
    unit.coverage.sample_case("xstage.fast_replay_reenters_pipeline")


def test_replay_cause_matrix_reaches_every_lq_cause_bit(unit):
    """Exercise the remaining replay causes at the S2 stage: SQ data invalid
    (4), bank conflict (8), RAR nack (9) and RAW nack (10)."""
    def beat_then(stage_inp, label):
        unit.cycle(CycleInput.idle().issue(issue(off=0, rob=0x50)),
                   f"{label} t0")
        unit.cycle(CycleInput.idle().translated(translation(off=0)),
                   f"{label} t1")
        return unit.cycle(stage_inp, f"{label} t2")

    got = beat_then(idle().with_sq_data_invalid(first_flag=1), "cause4")
    assert got.s3.lq.replay_cause(ReplayCause.SQ_DATA_INVALID)

    got = beat_then(idle().with_dcache(bank_conflict=True), "cause8")
    assert got.s3.lq.replay_cause(ReplayCause.BANK_CONFLICT)

    got = beat_then(idle().without_rar_ready(), "cause9")
    assert got.s3.lq.replay_cause(ReplayCause.RAR_NACK)

    got = beat_then(idle().without_raw_ready(), "cause10")
    assert got.s3.lq.replay_cause(ReplayCause.RAW_NACK)
    # A following clean beat drops the one-hot back to zero.
    unit.cycle(CycleInput.idle().issue(issue(off=0x40, rob=0x51)),
               "cause10 clear t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0x40)),
               "cause10 clear t1")
    got = unit.cycle(idle(), "cause10 clear t2")
    assert not got.s3.lq.replay_cause(ReplayCause.RAW_NACK)
    unit.coverage.sample_case("xstage.lq_write_cause_encoding")


def test_tail_merge_takes_the_mshr_id_from_the_head_beat(unit):
    """A crossing head with a DCache miss leaves cause_6 in the S4 concat beat;
    the merged LQ entry must report the head's MSHR id and handled flag."""
    unit.cycle(CycleInput.idle().issue(issue(off=0x1C, rob=0x66)), "mshr t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0x1C)), "mshr t1")
    head = CycleInput.idle().translated(translation(off=0x20)).with_dcache_read(
        DcacheRead(miss=True, mshr_id=0xA, handled=True))
    unit.cycle(head, "mshr t2")
    seen = [unit.cycle(idle(), f"mshr t{index + 3}") for index in range(4)]
    merged = [obs for obs in seen
              if obs.s3.lq.valid
              and obs.s3.lq.replay_cause(ReplayCause.DCACHE_MISS)]
    assert merged, "the head carries cause_6 into the merged LQ entry"
    got = merged[0]
    assert got.s3.lq.mshr_id == 0xA
    assert got.s3.lq.handled_by_mshr == 1
    unit.coverage.sample_case("xstage.tail_data_merge")


def test_unaligned_heads_exercise_every_tail_address_bit(unit):
    """Walking-one over the line address of a crossing load: the injected tail
    advances one 16B line, so its vaddr/fullva/mask wires see every bit."""
    seen_vaddr = 0
    seen_fullva = 0
    for bit in range(4, 46):
        vaddr = (1 << bit) & ((1 << 50) - 1)
        inp = issue(off=0x1C, src=vaddr, rob=bit & 0xFF)
        unit.cycle(CycleInput.idle().issue(inp), f"tail bit {bit} t0")
        tlb = Translation(paddr=(1 << (bit % 48)),
                          paddr_1=(1 << (bit % 48)), fullva=vaddr)
        unit.cycle(CycleInput.idle().translated(tlb), f"tail bit {bit} t1")
        # The injected tail is translated one cycle later.
        tail_tlb = Translation(
            paddr=((1 << (bit % 48)) + 0x10) & ((1 << 48) - 1),
            paddr_1=((1 << (bit % 48)) + 0x10) & ((1 << 48) - 1),
            fullva=(vaddr + 0x10) & ((1 << 64) - 1))
        unit.cycle(CycleInput.idle().translated(tail_tlb),
                   f"tail bit {bit} t2")
        for extra in range(4):
            got = unit.cycle(idle(), f"tail bit {bit} t{3 + extra}")
            seen_vaddr |= got.s3.lq.vaddr if got.s3.lq.valid else 0
            seen_fullva |= got.s3.lq.fullva if got.s3.lq.valid else 0
    assert seen_vaddr & 0x3FFF_FFFF_FFF0, hex(seen_vaddr)
    assert seen_fullva, hex(seen_fullva)
    unit.coverage.sample_case("xstage.cross_16b_head_tail_loopback")


def test_ldin_fuoptype_walking_one(unit):
    """All 12 bits of the ExuInput fuOpType reach S0's scalar payload; the
    load semantics only decode a few of them, but the port must be exercised."""
    for bit in range(12):
        inp = issue(fu=1 << bit, off=0, rob=0x70)
        unit.cycle(CycleInput.idle().issue(inp), f"fu bit {bit} t0")
        unit.cycle(CycleInput.idle().translated(translation(off=0)),
                   f"fu bit {bit} t1")
        unit.cycle(idle(), f"fu bit {bit} t2")
        unit.cycle(idle(), f"fu bit {bit} drain")


def test_prefetch_train_carries_every_meta_source(unit):
    for meta in range(8):
        unit.cycle(CycleInput.idle().issue(issue(off=0, rob=0x40 + meta)),
                   f"meta {meta} t0")
        tlb = CycleInput.idle().translated(translation(off=0)).with_dcache_read(
            DcacheRead(meta_prefetch=meta))
        unit.cycle(tlb, f"meta {meta} t1")
        for extra in range(3):
            idle_inp = idle().with_dcache_read(
                DcacheRead(meta_prefetch=meta))
            got = unit.cycle(idle_inp, f"meta {meta} t{2 + extra}")
            if got.prefetch_train.valid:
                assert got.prefetch_train.meta_source == meta
    # One last training beat with metaSource 0 clears the high bit again.
    unit.cycle(CycleInput.idle().issue(issue(off=0x80, rob=0x50)),
               "meta clear t0")
    tlb = CycleInput.idle().translated(translation(off=0x80)).with_dcache_read(
        DcacheRead(meta_prefetch=0))
    unit.cycle(tlb, "meta clear t1")
    unit.cycle(idle(), "meta clear t2")
    unit.coverage.sample_case("xstage.prefetch_train_pulse")


def test_nuke_cause_sets_and_clears_the_highest_one_hot_bit(unit):
    # A matching store nuke while the load is in S2 raises cause 11; the next
    # clean beat must clear it again.
    unit.cycle(CycleInput.idle().issue(issue(off=0, rob=0x20, lq=1, sq=2)),
               "nuke t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0)), "nuke t1")
    nuke = idle().with_nuke(0, NukeQuery(
        valid=True, rob=RobTag(value=4), paddr=0x2000, mask=0xFFFF,
        match_type=2))
    got = unit.cycle(nuke, "nuke t2")
    assert got.s3.lq.replay_cause(ReplayCause.NUKE)
    # A following clean beat replaces the S3 input and clears the one-hot.
    unit.cycle(CycleInput.idle().issue(issue(off=0x40, rob=0x22)),
               "nuke t3")
    unit.cycle(CycleInput.idle().translated(translation(off=0x40)),
               "nuke t4")
    got = unit.cycle(idle(), "nuke t5")
    assert not got.s3.lq.replay_cause(ReplayCause.NUKE)
    unit.coverage.sample_case("xstage.nuke_query_fields")


def test_misaligned_uncache_load_sets_address_misaligned(unit):
    # 8B at offset 4 with an NC PBMT: S0 marks the beat unaligned, S2 turns it
    # into the AM exception instead of an access fault.
    unit.cycle(CycleInput.idle().issue(issue(off=0x04)), "am t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0x04, pbmt=1)),
               "am t1")
    got = unit.cycle(idle(), "am t2")
    assert got.s3.ldout.exceptions.load_address_misaligned
    assert got.s3.exception_info.exceptions.load_address_misaligned
    assert got.s3.lq.exceptions.load_address_misaligned
    # A following clean load clears the bit again.
    unit.cycle(CycleInput.idle().issue(issue(off=0x40)), "am t3")
    unit.cycle(CycleInput.idle().translated(translation(off=0x40)), "am t4")
    got = unit.cycle(idle(), "am t5")
    assert not got.s3.ldout.exceptions.load_address_misaligned


def test_fp_and_vector_v0_register_writes(unit):
    fp = issue(off=0, rf_wen=False, fp_wen=True)
    unit.cycle(CycleInput.idle().issue(fp), "fp t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0)), "fp t1")
    got = unit.cycle(idle(), "fp t2")
    assert got.s3.fp_rf.valid == 1
    assert got.s3.int_rf.valid == 0

    vec = issue(off=0x80, rf_wen=False, vec_wen=True, v0_wen=True)
    unit.cycle(CycleInput.idle().issue(vec), "vec t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0x80)), "vec t1")
    got = unit.cycle(idle(), "vec t2")
    assert got.s3.vec_rf.valid == 1
    assert got.s3.v0_rf.valid == 1
    assert got.s3.vector_wakeup.wen == 1
    # A following scalar load clears the vector wakeup.
    unit.cycle(CycleInput.idle().issue(issue(off=0xC0)), "vec t3")
    unit.cycle(CycleInput.idle().translated(translation(off=0xC0)), "vec t4")
    got = unit.cycle(idle(), "vec t5")
    assert got.s3.vec_rf.valid == 0
    assert got.s3.v0_rf.valid == 0


def test_rr_bank_conflict_fast_replay_is_accepted_and_reenters(unit):
    """A bank-conflict replay with the RR grant is handed back to S0 in the
    same cycle the beat sits in S2 (the candidate pulse is combinational), so
    the observable contract is that this beat is not committed and later
    returns to the pipeline with the same address."""
    unit.cycle(CycleInput.idle().issue(issue(off=0, rob=0x19)), "rr t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0)), "rr t1")
    conflict = idle().with_dcache(bank_conflict=True, rr_conflict=True).with_rr_grant()
    unit.cycle(conflict, "rr t2")
    committed = []
    for index in range(10):
        got = unit.cycle(idle(), f"rr t{3 + index}")
        if got.s3.lq.valid and got.s3.ldout.valid:
            committed.append(got.s3.lq.vaddr)
    assert committed, "the replayed beat must eventually commit"
    assert all(vaddr == 0x8000_0000 for vaddr in committed)
    unit.coverage.sample_case("xstage.fast_replay_reenters_pipeline")


def test_clean_head_with_a_replaying_tail_revokes_last_last_cycle(unit):
    # The head is clean but the tail needs a replay: S3 reports the head on
    # ``revokeLastLastCycle`` so the replay queue can drop it.
    unit.cycle(CycleInput.idle().issue(issue(off=0x1C, rob=0x31)), "rll t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0x1C)), "rll t1")
    head = CycleInput.idle().translated(translation(off=0x20))
    unit.cycle(head, "rll t2")
    tail = idle().with_dcache_read(DcacheRead(miss=True))
    got = unit.cycle(tail, "rll t3")
    assert got.s3.rar_revoke.last_last_cycle == 1
    assert got.s3.raw_revoke.last_last_cycle == 1
    # Push two more clean beats so the revoke pulse falls again.
    for index in range(2):
        unit.cycle(CycleInput.idle().issue(
            issue(off=0x40 * index, rob=0x32 + index)), f"rll t{4 + index}")
        unit.cycle(CycleInput.idle().translated(translation(off=0x40 * index)),
                   f"rll t{6 + index}")
        unit.cycle(idle(), f"rll t{8 + index}")
    got = unit.cycle(idle(), "rll t10")
    assert got.s3.rar_revoke.last_last_cycle == 0
    unit.coverage.sample_case("xstage.cross_16b_head_tail_loopback")


def test_prefetch_train_rob_index_and_software_prefetch_class(unit):
    """Check training identity and the software-prefetch class actually exposed."""
    for bit in range(8):
        unit.cycle(CycleInput.idle().issue(
            issue(off=0, rob=1 << bit, is_former=bit & 1)),
            f"train rob {bit} t0")
        unit.cycle(CycleInput.idle().translated(translation(off=0)),
                   f"train rob {bit} t1")
        for extra in range(2):
            unit.cycle(idle(), f"train rob {bit} t{2 + extra}")
    # There is no hardware-prefetch injection port at this parent. Replay
    # does not expose pftType; an invented entrance=0x20 cannot prove it.
    software = unit.cycle(CycleInput.idle().issue(issue(fu=0x01, off=0x300)),
                          "software prefetch t0")
    assert software.s1.sw_prefetch.valid == 1
    unit.cycle(CycleInput.idle().translated(translation(off=0x300)),
               "software prefetch t1")
    unit.cycle(idle(), "software prefetch t2")
    raw = unit.observe()
    # FU=1 sets noQuery in S0. S1 records tlbAccessResult=1, whereas S2
    # training requires bit[1] (a real TLB hit), so there is no train beat.
    assert raw.prefetch_train.valid == 0
    assert raw.prefetch_train.is_hw_prefetch == 0
    assert raw.prefetch_train.is_first_issue == 1
    unit.coverage.sample_case("xstage.prefetch_train_pulse")


def test_trigger_slot_three_fires_and_clears(unit):
    configs = [TriggerSlot() for _ in range(4)]
    configs[3] = TriggerSlot(match_type=MATCH_EQ, select=0, timing=0,
                               action=1, chain=0, store=1, tdata2=0x8000_0500)
    trigger = TriggerSettings(configs=configs, enables=[False, False, False, True],
                              debug_mode=False, can_raise_bp_exp=True)
    inp = CycleInput.idle().issue(issue(off=0x500)).with_trigger(trigger)
    unit.cycle(inp, "slot3 t0")
    tlb = CycleInput.idle().translated(translation(off=0x500)).with_trigger(trigger)
    unit.cycle(tlb, "slot3 t1")
    got = unit.cycle(idle(), "slot3 t2")
    assert got.s3.ldout.trigger == 1, "debug action code"
    assert not got.s3.ldout.exceptions.breakpoint
    # A following clean load reports the no-action code (0xF) again.
    unit.cycle(CycleInput.idle().issue(issue(off=0x540)), "slot3 t3")
    unit.cycle(CycleInput.idle().translated(translation(off=0x540)), "slot3 t4")
    got = unit.cycle(idle(), "slot3 t5")
    assert got.s3.ldout.trigger == 0xF
    unit.coverage.sample_case("xstage.trigger_breakpoint_propagates")


def test_uncache_first_access_reports_cause_zero(unit):
    # An ldin access that lands in NC space (pbmt=1) needs an uncache replay
    # before it can read memory: cause_0 on the first attempt.
    unit.cycle(CycleInput.idle().issue(issue(off=0x08, rob=0x23)), "nc t0")
    unit.cycle(CycleInput.idle().translated(translation(off=0x08, pbmt=1)),
               "nc t1")
    got = unit.cycle(idle(), "nc t2")
    assert got.s3.lq.replay_cause(ReplayCause.UNCACHE_FIRST_ACCESS)
    assert got.s3.ldout.valid == 0
    assert got.s2.dcache_kill == 1
    unit.coverage.sample_case("xstage.uncache_bypass_read")
    unit.coverage.sample_case("xstage.lq_write_cause_encoding")


def test_breakpoint_bit_sets_and_clears_across_stages(unit):
    trigger = TriggerSettings(
        configs=[TriggerSlot(match_type=MATCH_EQ, select=0, timing=0,
                               action=0, chain=0, store=1,
                               tdata2=0x8000_0600)]
                + [TriggerSlot() for _ in range(3)],
        enables=[True, False, False, False])
    inp = CycleInput.idle().issue(issue(off=0x600, rob=0x24)).with_trigger(trigger)
    unit.cycle(inp, "bp2 t0")
    tlb = CycleInput.idle().translated(translation(off=0x600)).with_trigger(trigger)
    unit.cycle(tlb, "bp2 t1")
    got = unit.cycle(idle(), "bp2 t2")
    assert got.s3.ldout.exceptions.breakpoint
    # A following clean load clears exceptionVec_3 in every stage register.
    for index in range(2):
        unit.cycle(CycleInput.idle().issue(
            issue(off=0x640 + 0x40 * index, rob=0x25 + index)),
            f"bp2 t{3 + index * 3}")
        unit.cycle(CycleInput.idle().translated(
            translation(off=0x640 + 0x40 * index)), f"bp2 t{4 + index * 3}")
        got = unit.cycle(idle(), f"bp2 t{5 + index * 3}")
    assert not got.s3.ldout.exceptions.breakpoint
    assert not got.s3.lq.exceptions.breakpoint


def test_fast_replay_nuke_first_uses_the_waiting_sq_index(unit):
    # A load with a store-set hit whose waitSqIdx matches the nuke request gets
    # ``fastReplayNukeFirst`` so the fast replay is not blocked by cause_2.
    # waitSqIdx_value 5 is the identity that must match the nuke request.
    load = LoadIssue(address=0x8000_0000, rob=RobTag(value=0x26), pdest=0x35,
                     lq_idx=3, sq_idx=2, fu_op=LD, store_set_hit=True,
                     wait_sq=SqTag(value=5))
    unit.cycle(CycleInput.idle().issue(load), "nukefirst t0")
    nuke = NukeQuery(valid=True, rob=RobTag(value=3), sq=SqTag(value=5),
                     paddr=0x2000, mask=0xFFFF, match_type=2)
    unit.cycle(CycleInput.idle().translated(translation(off=0)).with_nuke(0, nuke),
               "nukefirst t1")
    got = unit.cycle(idle(), "nukefirst t2")
    assert got.s3.lq.replay_cause(ReplayCause.NUKE)
    unit.coverage.sample_case("xstage.nuke_query_fields")
