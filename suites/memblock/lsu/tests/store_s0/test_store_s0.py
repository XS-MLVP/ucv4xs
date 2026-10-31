"""StoreUnitS0 UT: store address stage 0.

Covers arbitration, the fixed-latency pipeline register, the combinational TLB
request, scalar field synthesis, redirect kill, the illegal-issue check, and the
align / cross-16B / cross-page / address-ready qualifiers.

Timing convention: Picker evaluates combinationally inside ``Step``, so one
``run(...)`` call drives a cycle, clocks it, and returns the outputs *after*
that edge. A scalar request therefore produces its pipeOut beat in the same
call; the next call (with no request) produces an empty beat.
"""
from __future__ import annotations

import random

import pytest

from suites.memblock.lsu.pointers import LEVEL_FLUSH, LEVEL_FLUSH_AFTER, redirect, no_redirect
from suites.memblock.lsu.store_s0.coverage import S0_CASES, StoreS0Coverage
from suites.memblock.lsu.store_s0.env import (
    ENTRANCE_SCALAR_ISSUE,
    ENTRANCE_UNALIGN_TAIL,
    STIN_FIELDS,
    TAIL_FIELDS,
    StoreS0Env,
    blank,
    gen_vwmask128,
    random_stin,
    random_tail,
    sign_extend,
)


@pytest.fixture
def s0(dut_factory):
    dut = dut_factory("store_s0")
    env = StoreS0Env(dut, StoreS0Coverage())
    env.reset()
    return env


def run(s0, stin_valid=0, stin=None, tail_valid=0, tail=None, tail_cross4k=0,
        deq=(0, 0, 0), addr_ready=(0, 0, 0), redir=None, context="cycle"):
    return s0.cycle(stin_valid, stin or blank(STIN_FIELDS), tail_valid,
                    tail or blank(TAIL_FIELDS), tail_cross4k, deq, addr_ready,
                    redir or no_redirect(), context)


def stin_at(vaddr=0x1000, size=3, rob=5, sq=7, sq_second=0, fu_extra=0, **overrides):
    """Build a scalar stin whose computed vaddr equals ``vaddr`` (imm=0)."""
    fu = ((size & 0x7) << 1) | fu_extra
    values = dict(fuOpType=fu, src_0=vaddr, imm=0, robIdx_flag=0, robIdx_value=rob,
                  robIdx_isFormer=1, isRVC=0, ftqIdx_flag=0, ftqIdx_value=0,
                  ftqOffset=0, storeSetHit=0, ssid=0, sqIdx_first_flag=0,
                  sqIdx_second_flag=sq_second, sqIdx_value=sq)
    values.update(overrides)
    return values


def test_idle_cycle_outputs_nothing(s0):
    got = run(s0, context="idle")
    assert got["valid"] == 0
    assert got["stin_ready"] == 1
    assert got["tlb_valid"] == 0
    s0.coverage.sample_case("pipe.idle_outputs_invalid")


def test_reset_clears_the_pipeline_register(s0):
    assert int(s0.out_valid.value) == 0
    s0.coverage.sample_case("pipe.reset_clears_valid")


def test_scalar_request_is_registered_with_one_cycle_latency(s0):
    stin = stin_at(vaddr=0x1000, size=3, rob=5, sq=7)
    got = run(s0, 1, stin, context="drive")
    assert got["valid"] == 1
    assert got["bits"]["vaddr"] == 0x1000
    assert got["bits"]["size"] == 3
    assert got["bits"]["entrance"] == ENTRANCE_SCALAR_ISSUE
    assert got["bits"]["accessType_instrType"] == 1
    s0.coverage.sample_case("pipe.scalar_is_accepted_and_registered")
    # The beat is consumed in the cycle it appears: no backpressure exists.
    assert run(s0, 0, context="consumed")["valid"] == 0
    s0.coverage.sample_case("pipe.one_cycle_latency")


def test_every_pipeline_field_matches_the_reference(s0):
    rng = random.Random(11)
    for beat in range(40):
        size = rng.randrange(4)
        vaddr = rng.randrange(1 << 20)
        stin = random_stin(rng, src_0=vaddr, imm=0,
                           fuOpType=(size << 1) | (1 if rng.random() < 0.2 else 0))
        got = run(s0, 1, stin, context=f"field beat {beat}")
        assert got["valid"] == 1
        # The reference already compared every field; this asserts the intent.
        assert got["bits"]["size"] == size
    s0.coverage.sample_case("pipe.field_fidelity")


def test_unalign_tail_wins_over_scalar_and_blocks_ready(s0):
    stin = stin_at(vaddr=0x2000, rob=1, sq=3)
    tail = random_tail(random.Random(3), vaddr=0x2FF0, size=3)
    got = run(s0, 1, stin, 1, tail, context="both")
    assert got["stin_ready"] == 0
    assert got["tlb_valid"] == 1
    s0.coverage.sample_case("arb.tail_has_priority")
    s0.coverage.sample_case("arb.tail_blocks_stin_ready")
    assert got["valid"] == 1
    assert got["bits"]["entrance"] == ENTRANCE_UNALIGN_TAIL
    assert run(s0, 0, context="idle")["stin_ready"] == 1
    s0.coverage.sample_case("arb.scalar_ready_when_no_tail")


def test_tail_without_scalar_is_accepted(s0):
    tail = random_tail(random.Random(4), vaddr=0x3000, size=2)
    got = run(s0, 0, None, 1, tail, context="tail only")
    assert got["valid"] == 1
    assert got["bits"]["entrance"] == ENTRANCE_UNALIGN_TAIL
    assert got["bits"]["vaddr"] == 0x3000
    s0.coverage.sample_case("arb.tail_without_stin")


# ------------------------------------------------------------------- TLB req
def test_tlb_request_is_issued_for_the_selected_source(s0):
    stin = stin_at(vaddr=0x1234, size=2, rob=9, sq=1)
    got = run(s0, 1, stin, context="scalar tlb")
    assert got["tlb_valid"] == 1
    s0.coverage.sample_case("tlb.issued_for_scalar")
    tail = random_tail(random.Random(5), vaddr=0x4321, size=1)
    got = run(s0, 0, None, 1, tail, context="tail tlb")
    assert got["tlb_valid"] == 1
    s0.coverage.sample_case("tlb.issued_for_tail")
    got = run(s0, 0, context="idle tlb")
    assert got["tlb_valid"] == 0
    s0.coverage.sample_case("tlb.not_issued_when_idle")


def test_tlb_checkfullva_follows_instr_type(s0):
    scalar = random_tail(random.Random(6), accessType_instrType=1)
    run(s0, 0, None, 1, scalar, context="scalar type")
    assert int(s0.tlb["checkfullva"].value) == 1
    s0.coverage.sample_case("tlb.checkfullva_from_instr_type")
    prefetch = random_tail(random.Random(7), accessType_instrType=4)
    got = run(s0, 0, None, 1, prefetch, context="prefetch type")
    assert got["tlb_valid"] == 1
    assert int(s0.tlb["checkfullva"].value) == 0
    s0.coverage.sample_case("tlb.is_prefetch_bit")


def test_tlb_cmd_write_for_stores_and_cbo_zero_read_for_other_cbo(s0):
    """``cmd = {2'b0, ~isCboNoZero}``: TlbCmd.write(1) for stores and CBO.zero;
    TlbCmd.read(0) for the other CBO operations, which only need read permission."""
    plain_store = stin_at(size=3, fu_extra=0)
    run(s0, 1, plain_store, context="plain store")
    assert int(s0.tlb["cmd"].value) == 1
    cbo_zero = stin_at(size=3, fu_extra=1)   # fuOpType[0]=1 and size[3:1]==3 -> CBO.zero
    run(s0, 1, cbo_zero, context="cbo zero")
    assert int(s0.tlb["cmd"].value) == 1
    s0.coverage.sample_case("tlb.cmd_distinguishes_cbo_zero")
    cbo_line = stin_at(size=2, fu_extra=1)   # isCbo, not zero -> isCboNoZero=1
    run(s0, 1, cbo_line, context="cbo line")
    assert int(s0.tlb["cmd"].value) == 0


def test_tlb_hyperinst_decodes_fuoptype_bit6(s0):
    for fu_bit6, is_cbo, want in ((1, 0, 1), (1, 1, 0), (0, 0, 0)):
        stin = stin_at(size=3, fu_extra=is_cbo)
        stin["fuOpType"] = stin["fuOpType"] | (fu_bit6 << 6)
        got = run(s0, 1, stin, context=f"hyperinst bit6={fu_bit6} cbo={is_cbo}")
        assert got["tlb_valid"] == 1
        assert int(s0.tlb["hyperinst"].value) == want
    s0.coverage.sample_case("tlb.hyperinst_from_fuoptype")


def test_tlb_request_is_not_gated_by_redirect(s0):
    stin = stin_at(vaddr=0x5000, rob=12, sq=4)
    got = run(s0, 1, stin, redir=redirect(flag=0, value=12, former=1),
              context="killed but tlb")
    assert got["tlb_valid"] == 1
    assert got["valid"] == 0
    s0.coverage.sample_case("tlb.issued_even_when_killed")


# ------------------------------------------------------- scalar field synthesis
def test_vaddr_and_fullva_sign_extend_the_immediate(s0):
    stin = stin_at(vaddr=0, size=3, imm=0)
    stin["src_0"] = 0x8000_0000
    stin["imm"] = 0xFFF          # -1
    got = run(s0, 1, stin, context="neg imm")
    assert got["bits"]["vaddr"] == 0x7FFF_FFFF
    assert got["bits"]["fullva"] == 0x8000_0000 - 1
    s0.coverage.sample_case("scalar.vaddr_and_fullva_sign_extend")
    stin["src_0"] = 0
    stin["imm"] = 0x7FF          # +2047
    got = run(s0, 1, stin, context="pos imm")
    assert got["bits"]["vaddr"] == 0x7FF


def test_vaddr_is_truncated_to_50_bits(s0):
    stin = stin_at(vaddr=0, size=3)
    stin["src_0"] = (1 << 49) - 1
    stin["imm"] = 0x7FF
    got = run(s0, 1, stin, context="overflow")
    assert got["bits"]["vaddr"] == ((1 << 49) - 1 + 0x7FF) & ((1 << 50) - 1)
    assert got["bits"]["fullva"] == (1 << 49) - 1 + 0x7FF
    s0.coverage.sample_case("scalar.vaddr_wraps_to_50_bits")


def test_size_and_mask_come_from_fuoptype_and_offset(s0):
    for size, base in ((0, 0x1), (1, 0x3), (2, 0xF), (3, 0xFF)):
        stin = stin_at(vaddr=0x1005, size=size)
        got = run(s0, 1, stin, context=f"size {size}")
        assert got["bits"]["size"] == size
        assert got["bits"]["mask"] == (base << 5) & 0xFFFF
    s0.coverage.sample_case("scalar.size_from_fuoptype")
    s0.coverage.sample_case("scalar.mask_byte_offset")
    s0.coverage.sample_case("scalar.mask_shifts_by_16b_offset")


def test_cbo_mask_covers_the_whole_line_regardless_of_offset(s0):
    stin = stin_at(vaddr=0x1005, size=2, fu_extra=1)
    got = run(s0, 1, stin, context="cbo")
    assert got["bits"]["accessType_isCbo"] == 1
    assert got["bits"]["mask"] == 0xFFFF
    s0.coverage.sample_case("scalar.mask_cbo_full_line")


# ------------------------------------------------------------------- kills
@pytest.mark.parametrize("case", ["same_slot", "flush_after", "younger", "invalid",
                                  "former", "wrap"])
def test_redirect_kill_matrix(s0, case):
    rob_value, rob_former = 20, 1
    stin = stin_at(vaddr=0x6000, rob=rob_value, sq=2)
    stin["robIdx_isFormer"] = rob_former
    redir = {
        "same_slot": redirect(flag=0, value=20, former=1, level=LEVEL_FLUSH),
        "flush_after": redirect(flag=0, value=19, former=1, level=LEVEL_FLUSH_AFTER),
        "younger": redirect(flag=0, value=21, former=1, level=LEVEL_FLUSH_AFTER),
        "invalid": redirect(flag=0, value=20, former=1, level=LEVEL_FLUSH, valid=0),
        "former": redirect(flag=0, value=20, former=0, level=LEVEL_FLUSH_AFTER),
        "wrap": redirect(flag=1, value=100, former=1, level=LEVEL_FLUSH_AFTER),
    }[case]
    got = run(s0, 1, stin, redir=redir, context=f"kill {case}")
    expected = {"same_slot": 0, "flush_after": 0, "younger": 1, "invalid": 1,
                "former": 1, "wrap": 0}[case]
    assert got["valid"] == expected, f"{case}: valid {got['valid']} != {expected}"
    s0.coverage.sample_case({
        "same_slot": "kill.same_slot_flush",
        "flush_after": "kill.flush_after_older",
        "younger": "kill.younger_target_survives",
        "invalid": "kill.invalid_redirect_survives",
        "former": "kill.former_ordering",
        "wrap": "kill.wrap_flag_ordering",
    }[case])


# ------------------------------------------------------------ illegal issue
def test_illegal_issue_window_is_the_next_64_sq_slots(s0):
    """The legal window is [deq, deq+64) in {second_flag, value} operation space.

    With deq=(first=0, second=0, value=10) the operation value is 10, so slots
    10..63 (second=0) and 64..73 (second=1) are inside the window.
    """
    deq = (0, 0, 10)
    cases = [
        ((0, 10), 0),   # first slot of the window
        ((0, 63), 0),   # last slot of the low half
        ((1, 0), 0),    # operation value 64 is still inside
        ((1, 9), 0),    # operation value 73 is the last legal slot
        ((1, 10), 1),   # operation value 74 is exactly the end pointer
        ((0, 9), 1),    # one slot before the window
        ((0, 0), 1),    # far before the window
    ]
    for (second, value), expected in cases:
        stin = stin_at(vaddr=0x7000, sq=value, sq_second=second)
        got = run(s0, 1, stin, deq=deq, context=f"illegal second={second} value={value}")
        assert got["bits"]["illegalIssue"] == expected, f"second={second} value={value}"
    s0.coverage.sample_case("illegal.sqidx_inside_window_legal")
    s0.coverage.sample_case("illegal.sqidx_at_window_end_illegal")
    s0.coverage.sample_case("illegal.sqidx_before_deq_illegal")


def test_illegal_issue_window_wraps_with_the_flag(s0):
    """deq=(first=1, second=1, value=60) has operation value 124.

    ``endPtr = {first, second, value} + 64`` = (0, 0, 60), so the legal window is
    exactly the four slots with operation value 124..127: (second=1, 60..63)
    with the matching first flag. Every other slot is illegal.
    """
    deq = (1, 1, 60)
    stin_first = 1
    cases = [
        (1, 60, 0), (1, 61, 0), (1, 62, 0), (1, 63, 0),   # the whole window
        (1, 59, 1),                                        # one below
        (0, 60, 1),                                        # wrong second flag
        (0, 0, 1), (0, 63, 1),                             # low half is outside
    ]
    for second, value, want in cases:
        stin = stin_at(sq=value, sq_second=second)
        stin["sqIdx_first_flag"] = stin_first
        got = run(s0, 1, stin, deq=deq, context=f"wrap {second},{value}")
        assert got["bits"]["illegalIssue"] == want, f"second={second} value={value}"
    # A mismatched first flag puts the instruction in the other wrap generation.
    stin = stin_at(sq=60, sq_second=1)
    stin["sqIdx_first_flag"] = 0
    got = run(s0, 1, stin, deq=deq, context="wrap first mismatch")
    assert got["bits"]["illegalIssue"] == 1
    s0.coverage.sample_case("illegal.wrap_window")


# -------------------------------------------------------------- qualifiers
@pytest.mark.parametrize("vaddr,size,align", [
    (0x1000, 0, 1), (0x1001, 0, 1),
    (0x1000, 1, 1), (0x1001, 1, 0),
    (0x1000, 2, 1), (0x1002, 2, 0),
    (0x1000, 3, 1), (0x1004, 3, 0),
])
def test_align_flag_follows_size_and_address(s0, vaddr, size, align):
    stin = stin_at(vaddr=vaddr, size=size)
    got = run(s0, 1, stin, context="align")
    assert got["bits"]["align"] == align, f"vaddr={vaddr:#x} size={size}"
    s0.coverage.sample_case("align.scalar_aligned_by_size" if align
                            else "align.scalar_misaligned")


def test_cbo_and_prefetch_force_align_and_suppress_unalign_head(s0):
    stin = stin_at(vaddr=0x1005, size=3, fu_extra=1)
    got = run(s0, 1, stin, context="cbo")
    assert got["bits"]["align"] == 1
    assert got["bits"]["unalignHead"] == 0
    assert got["bits"]["cross4KPage"] == 0
    s0.coverage.sample_case("align.cbo_forced_aligned")
    s0.coverage.sample_case("cross4k.cbo_never_crosses_page")

    prefetch = random_tail(random.Random(8), accessType_instrType=4,
                           vaddr=0x100F, size=3, mask=0xFFFF)
    got = run(s0, 0, None, 1, prefetch, context="prefetch")
    assert got["bits"]["align"] == 1
    assert got["bits"]["unalignHead"] == 0
    s0.coverage.sample_case("align.prefetch_forced_aligned")


def test_tail_is_forced_unaligned_and_suppresses_unalign_head(s0):
    tail = random_tail(random.Random(9), vaddr=0x2008, size=3,
                       accessType_instrType=1, accessType_isCbo=0)
    got = run(s0, 0, None, 1, tail, context="tail")
    assert got["bits"]["align"] == 0
    assert got["bits"]["unalignHead"] == 0
    s0.coverage.sample_case("align.tail_forced_unaligned")
    s0.coverage.sample_case("unalignhead.tail_suppressed")


@pytest.mark.parametrize("vaddr,size,cross", [
    (0x1000, 3, 0),   # bytes 0..7
    (0x1008, 3, 0),   # bytes 8..15: still the same 16B word
    (0x1009, 3, 1),   # bytes 9..16: crosses
    (0x100F, 0, 0),   # one byte at 15
    (0x100E, 2, 1),   # bytes 14..17: crosses
    (0x100C, 2, 0),   # bytes 12..15: same word
])
def test_scalar_cross_16b_detection(s0, vaddr, size, cross):
    stin = stin_at(vaddr=vaddr, size=size)
    got = run(s0, 1, stin, context="cross16")
    assert got["bits"]["unalignHead"] == cross, f"vaddr={vaddr:#x} size={size}"
    s0.coverage.sample_case("unalignhead.scalar_crosses_16b" if cross
                            else "unalignhead.scalar_within_16b")


@pytest.mark.parametrize("vaddr,size,cross", [
    (0x1000, 3, 0),   # bytes 0..7
    (0x1FF8, 3, 0),   # bytes 4088..4095: still inside the page
    (0x1FFF, 0, 0),   # one byte at the last page offset
    (0x1FFE, 2, 1),   # bytes 4094..4097: crosses
    (0x1FFC, 3, 1),   # bytes 4092..4099: crosses
    (0x1FFC, 2, 0),   # bytes 4092..4095: same page
])
def test_scalar_cross_page_detection(s0, vaddr, size, cross):
    stin = stin_at(vaddr=vaddr, size=size)
    got = run(s0, 1, stin, context="cross4k")
    assert got["bits"]["cross4KPage"] == cross, f"vaddr={vaddr:#x} size={size}"
    s0.coverage.sample_case("cross4k.scalar_crosses_page" if cross
                            else "cross4k.scalar_within_page")


def test_tail_inherits_cross_page_from_its_input(s0):
    tail = random_tail(random.Random(10), vaddr=0x2000, size=3,
                       accessType_instrType=1, accessType_isCbo=0)
    for injected in (0, 1):
        got = run(s0, 0, None, 1, tail, tail_cross4k=injected,
                  context="tail cross4k")
        assert got["bits"]["cross4KPage"] == injected
    s0.coverage.sample_case("cross4k.tail_inherits_from_input")


def test_is_addr_ready_head_is_a_full_sqptr_compare(s0):
    stin = stin_at(sq=7)
    got = run(s0, 1, stin, addr_ready=(0, 0, 7), context="match")
    assert got["bits"]["isAddrReadyHead"] == 1
    s0.coverage.sample_case("addrready.match")
    got = run(s0, 1, stin, addr_ready=(0, 0, 8), context="no match")
    assert got["bits"]["isAddrReadyHead"] == 0
    # The second flag must also participate.
    got = run(s0, 1, stin, addr_ready=(0, 1, 7), context="second flag")
    assert got["bits"]["isAddrReadyHead"] == 0
    s0.coverage.sample_case("addrready.no_match")


# ------------------------------------------------------------------ random
def test_seeded_random_stream_matches_the_model(s0):
    rng = random.Random(20261025)
    for cycle in range(500):
        stin_valid = 1 if rng.random() < 0.7 else 0
        tail_valid = 1 if rng.random() < 0.2 else 0
        size = rng.randrange(4)
        stin = random_stin(rng, src_0=rng.randrange(1 << 50),
                           imm=rng.randrange(1 << 12),
                           fuOpType=(size << 1) | (1 if rng.random() < 0.15 else 0))
        tail = random_tail(rng, vaddr=rng.randrange(1 << 50), size=rng.randrange(4))
        redir = no_redirect()
        if rng.random() < 0.3:
            redir = redirect(flag=rng.randrange(2),
                             value=rng.randrange(160),
                             former=rng.randrange(2),
                             level=rng.randrange(2))
        deq = (rng.randrange(2), rng.randrange(2), rng.randrange(64))
        addr_ready = (rng.randrange(2), rng.randrange(2), rng.randrange(64))
        run(s0, stin_valid, stin, tail_valid, tail, rng.randrange(2), deq,
            addr_ready, redir, context=f"random {cycle}")


def test_case_inventory_is_exact():
    assert len(S0_CASES) == len(set(S0_CASES))
    assert len(S0_CASES) == 47


def test_helper_functions_are_independent_of_the_dut():
    assert sign_extend(0xFFF, 12, 50) == -1
    assert sign_extend(0x7FF, 12, 50) == 0x7FF
    assert gen_vwmask128(0, 0) == 0x1
    assert gen_vwmask128(0xF, 0) == 0x8000
    assert gen_vwmask128(0, 3) == 0xFF


# ------------------------------------------------------- Q-size stores (4..7)
@pytest.mark.parametrize("size", [4, 5, 6, 7])
def test_q_size_store_uses_full_line_mask_and_q_byte_offset(s0, size):
    """``MemorySize.Q`` is encoded as ``b1??``, so sizes 4..7 all mean a 16B store:
    mask base 0xFFFF, byte offset 15, and alignment requires vaddr[3:0]==0."""
    stin = stin_at(vaddr=0x1010, size=size)
    got = run(s0, 1, stin, context=f"q size {size}")
    assert got["bits"]["size"] == size
    assert got["bits"]["mask"] == 0xFFFF
    assert got["bits"]["align"] == 1
    stin = stin_at(vaddr=0x1004, size=size)
    got = run(s0, 1, stin, context=f"q misaligned {size}")
    assert got["bits"]["align"] == 0


# ------------------------------------------------------- full-width toggling
def test_operand_and_opcode_full_width_are_exercised(s0):
    """Walk a single one across src_0, imm and fuOpType.

    ``src_0`` and ``imm`` feed the address adder, and ``fuOpType`` carries the
    size, the CBO flag and the hyper-instruction bit, so every bit of them is
    architecturally meaningful at this boundary.
    """
    for bit in range(64):
        stin = stin_at(size=3)
        stin["src_0"] = 1 << bit
        run(s0, 1, stin, context=f"src_0 bit {bit}")
    for bit in range(12):
        stin = stin_at(size=3)
        stin["imm"] = 1 << bit
        run(s0, 1, stin, context=f"imm bit {bit}")
    for bit in range(12):
        stin = stin_at(size=0)
        stin["fuOpType"] = 1 << bit
        run(s0, 1, stin, context=f"fuOpType bit {bit}")
    # Return every operand to zero so the opposite toggle direction is seen too.
    run(s0, 1, stin_at(size=0), context="clear")


def test_entrance_and_size_fields_toggle_all_bits(s0):
    """The entrance one-hot and the size field must be walked through all bits."""
    for entrance in (0x1, 0x2, 0x4, 0x8):
        tail = random_tail(random.Random(entrance), vaddr=0x1000, size=1,
                           accessType_isCbo=0, accessType_instrType=entrance & 0x7)
        run(s0, 0, None, 1, tail, context=f"entrance-ish {entrance:#x}")
    for size in range(8):
        run(s0, 1, stin_at(vaddr=0x1000, size=size), context=f"size {size}")
    for size in range(7, -1, -1):
        run(s0, 1, stin_at(vaddr=0x1000, size=size), context=f"size down {size}")


def test_immediate_port_full_width_and_q_size_tail(s0):
    """Walk all 64 bits of the imm port (only [11:0] are used, but the upper bits
    are real port bits) and exercise the full size field on the tail source."""
    for bit in range(64):
        stin = stin_at(size=3)
        stin["imm"] = 1 << bit
        run(s0, 1, stin, context=f"imm64 bit {bit}")
    run(s0, 1, stin_at(size=3), context="imm clear")
    for size in range(8):
        tail = random_tail(random.Random(100 + size), vaddr=0x1000, size=size,
                           accessType_isCbo=0, accessType_instrType=1)
        run(s0, 0, None, 1, tail, context=f"tail size {size}")
    for size in range(7, -1, -1):
        tail = random_tail(random.Random(200 + size), vaddr=0x1000, size=size,
                           accessType_isCbo=0, accessType_instrType=1)
        run(s0, 0, None, 1, tail, context=f"tail size down {size}")
