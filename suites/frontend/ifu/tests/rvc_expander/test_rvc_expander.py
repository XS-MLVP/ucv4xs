"""RvcExpander: architectural expansion, legality and statelessness."""

from __future__ import annotations

import random

import pytest

from suites.frontend.ifu.legacy_pins import P
from suites.frontend.ifu.model import cenc
from suites.frontend.ifu.model import isa
from suites.frontend.ifu.model.rvc import Expansion
from suites.frontend.ifu.model.rvc import expand


def observe(harness, word: int, fs_is_off: int = 0) -> tuple[int, int]:
    harness.set(io_in=word, io_fsIsOff=fs_is_off)
    harness.settle()
    return harness.read(P.p_out_bits), harness.read(P.p_ill)


def check(harness, word: int, expected: Expansion, *, fs_is_off: int = 0) -> None:
    bits, ill = observe(harness, word, fs_is_off)
    assert ill == int(expected.ill), (
        f"{word:#06x}: ill {ill} != {int(expected.ill)} ({expected.form})")
    if not expected.ill and not expected.hint:
        assert bits == expected.bits, (
            f"{word:#06x} ({expected.form}): expansion {bits:#010x} != {expected.bits:#010x}")


# ---------------------------------------------------------------------------
# Directed architectural families
# ---------------------------------------------------------------------------
INTEGER_CASES = [
    (cenc.c_nop(), isa.nop(), "c.nop"),
    (cenc.c_addi(10, 1), isa.addi(10, 10, 1), "c.addi"),
    (cenc.c_addi(5, -1), isa.addi(5, 5, -1), "c.addi negative"),
    (cenc.c_addiw(10, 7), isa.addiw(10, 10, 7), "c.addiw"),
    (cenc.c_addiw(3, -32), isa.addiw(3, 3, -32), "c.addiw negative"),
    (cenc.c_li(10, -1), isa.addi(10, 0, -1), "c.li"),
    (cenc.c_li(1, 31), isa.addi(1, 0, 31), "c.li positive"),
    (cenc.c_lui(10, 1), isa.lui(10, 1), "c.lui"),
    (cenc.c_lui(7, -1), isa.lui(7, 0xFFFFF), "c.lui negative"),
    (cenc.c_addi16sp(-16), isa.addi(2, 2, -16), "c.addi16sp"),
    (cenc.c_addi16sp(496), isa.addi(2, 2, 496), "c.addi16sp large"),
    (cenc.c_addi4spn(10, 16), isa.addi(10, 2, 16), "c.addi4spn"),
    (cenc.c_addi4spn(15, 1020), isa.addi(15, 2, 1020), "c.addi4spn max"),
    (cenc.c_slli(10, 3), isa.i_type(0x13, 10, 1, 10, 3), "c.slli"),
    (cenc.c_slli(10, 33), isa.i_type(0x13, 10, 1, 10, 33), "c.slli RV64"),
    (cenc.c_srli(10, 4), isa.i_type(0x13, 10, 5, 10, 4), "c.srli"),
    (cenc.c_srai(10, 4), isa.i_type(0x13, 10, 5, 10, 4 | 0x400), "c.srai"),
    (cenc.c_andi(10, -1), isa.i_type(0x13, 10, 7, 10, -1), "c.andi"),
    (cenc.c_sub(10, 11), isa.sub(10, 10, 11), "c.sub"),
    (cenc.c_xor(10, 11), isa.r_type(0x33, 10, 4, 10, 11, 0), "c.xor"),
    (cenc.c_or(10, 11), isa.r_type(0x33, 10, 6, 10, 11, 0), "c.or"),
    (cenc.c_and(10, 11), isa.r_type(0x33, 10, 7, 10, 11, 0), "c.and"),
    (cenc.c_subw(10, 11), isa.subw(10, 10, 11), "c.subw"),
    (cenc.c_addw(10, 11), isa.addw(10, 10, 11), "c.addw"),
    (cenc.c_mul(10, 11), isa.mul(10, 10, 11), "c.mul"),
]

MEMORY_CASES = [
    (cenc.c_lw(10, 11, 4), isa.load_bytes(2, 10, 11, 4), "c.lw"),
    (cenc.c_lw(8, 15, 124), isa.load_bytes(2, 8, 15, 124), "c.lw high"),
    (cenc.c_ld(10, 11, 8), isa.load_bytes(3, 10, 11, 8), "c.ld"),
    (cenc.c_ld(8, 15, 248), isa.load_bytes(3, 8, 15, 248), "c.ld high"),
    (cenc.c_sw(10, 11, 4), isa.store_bytes(2, 11, 10, 4), "c.sw"),
    (cenc.c_sd(10, 11, 8), isa.store_bytes(3, 11, 10, 8), "c.sd"),
    (cenc.c_fld(10, 11, 8), isa.fp_load_bytes(3, 10, 11, 8), "c.fld"),
    (cenc.c_fsd(10, 11, 8), isa.fp_store_bytes(3, 11, 10, 8), "c.fsd"),
    (cenc.c_lwsp(10, 4), isa.load_bytes(2, 10, 2, 4), "c.lwsp"),
    (cenc.c_ldsp(10, 8), isa.load_bytes(3, 10, 2, 8), "c.ldsp"),
    (cenc.c_swsp(10, 4), isa.store_bytes(2, 2, 10, 4), "c.swsp"),
    (cenc.c_sdsp(10, 8), isa.store_bytes(3, 2, 10, 8), "c.sdsp"),
    (cenc.c_fldsp(10, 8), isa.fp_load_bytes(3, 10, 2, 8), "c.fldsp"),
    (cenc.c_fsdsp(10, 8), isa.fp_store_bytes(3, 2, 10, 8), "c.fsdsp"),
]

CONTROL_CASES = [
    (cenc.c_j(8), isa.jal(0, 8), "c.j forward"),
    (cenc.c_j(-2), isa.jal(0, -2), "c.j backward"),
    (cenc.c_j(2046), isa.jal(0, 2046), "c.j max"),
    (cenc.c_beqz(10, 8), isa.beq(10, 0, 8), "c.beqz"),
    (cenc.c_beqz(15, -8), isa.beq(15, 0, -8), "c.beqz backward"),
    (cenc.c_bnez(10, 4), isa.bne(10, 0, 4), "c.bnez"),
    (cenc.c_bnez(8, -2), isa.bne(8, 0, -2), "c.bnez backward"),
    (cenc.c_jr(1), isa.jalr(0, 1, 0), "c.jr"),
    (cenc.c_jr(15), isa.jalr(0, 15, 0), "c.jr rs1"),
    (cenc.c_jalr(1), isa.jalr(1, 1, 0), "c.jalr"),
    (cenc.c_mv(10, 11), isa.addi(10, 11, 0), "c.mv"),
    (cenc.c_add(10, 11), isa.add(10, 10, 11), "c.add"),
    (cenc.c_ebreak(), isa.ebreak(), "c.ebreak"),
]

ZCB_CASES = [
    (cenc.c_lbu(10, 11, 0), isa.load_bytes(4, 10, 11, 0), "c.lbu 0"),
    (cenc.c_lbu(10, 11, 3), isa.load_bytes(4, 10, 11, 3), "c.lbu 3"),
    (cenc.c_lhu(10, 11, 2), isa.load_bytes(5, 10, 11, 2), "c.lhu"),
    (cenc.c_lh(10, 11, 2), isa.load_bytes(1, 10, 11, 2), "c.lh"),
    (cenc.c_sb(10, 11, 3), isa.store_bytes(0, 11, 10, 3), "c.sb"),
    (cenc.c_sh(10, 11, 2), isa.store_bytes(1, 11, 10, 2), "c.sh"),
    (cenc.c_zext_b(10), isa.i_type(0x13, 10, 7, 10, 0xFF), "c.zext.b"),
    (cenc.c_sext_b(10), isa.i_type(0x13, 10, 1, 10, 0x604), "c.sext.b"),
    (cenc.c_zext_h(10), isa.r_type(0x3B, 10, 4, 10, 0, 4), "c.zext.h"),
    (cenc.c_sext_h(10), isa.i_type(0x13, 10, 1, 10, 0x605), "c.sext.h"),
    (cenc.c_zext_w(10), isa.r_type(0x3B, 10, 0, 10, 0, 4), "c.zext.w"),
    (cenc.c_not(10), isa.i_type(0x13, 10, 4, 10, 0xFFF), "c.not"),
]


def _check_table(harness, table):
    for word, expected_bits, label in table:
        expected = Expansion(expected_bits, False, form=label)
        check(harness, word, expected)


@pytest.mark.feature("IFU-RVC-002")
def test_integer_forms(rvc_expander):
    _check_table(rvc_expander, INTEGER_CASES)


@pytest.mark.feature("IFU-RVC-003")
def test_memory_forms(rvc_expander):
    _check_table(rvc_expander, MEMORY_CASES)


@pytest.mark.feature("IFU-RVC-004")
def test_control_forms(rvc_expander):
    _check_table(rvc_expander, CONTROL_CASES)


@pytest.mark.feature("IFU-RVC-008")
def test_zcb_forms(rvc_expander):
    _check_table(rvc_expander, ZCB_CASES)


@pytest.mark.feature("IFU-RVC-001")
def test_full_width_passthrough(rvc_expander):
    words = [isa.addi(1, 2, 3), isa.jal(1, 16), isa.load_bytes(3, 5, 6, 8),
             isa.store_bytes(2, 7, 8, 12), isa.ebreak(), 0xFFFFFFFF, 0x00000003]
    for word in words:
        for fs in (0, 1):
            bits, ill = observe(rvc_expander, word, fs)
            assert (bits, ill) == (word, 0)


# ---------------------------------------------------------------------------
# Floating point and FS state
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-RVC-005")
def test_float_forms_follow_fs_state(rvc_expander):
    fp_words = [cenc.c_fld(10, 11, 8), cenc.c_fsd(10, 11, 8),
                cenc.c_fldsp(10, 8), cenc.c_fsdsp(10, 8)]
    for word in fp_words:
        expected = expand(word, fs_is_off=False)
        assert not expected.ill
        check(rvc_expander, word, expected, fs_is_off=0)
        bits, ill = observe(rvc_expander, word, 1)
        assert ill == 1, f"{word:#06x}: FP form must be illegal when FS is off"
    # Integer compressed forms do not depend on FS.
    for word, _, _ in INTEGER_CASES + ZCB_CASES:
        check(rvc_expander, word, expand(word, fs_is_off=False), fs_is_off=0)
        check(rvc_expander, word, expand(word, fs_is_off=True), fs_is_off=1)


# ---------------------------------------------------------------------------
# Reserved and hint encodings
# ---------------------------------------------------------------------------
RESERVED = {
    0x0000: "all-zero c.addi4spn immediate",
    0x2000: "c.fld with FS off",
    0xA000: "c.fsd with FS off",
    0x2002: "c.fldsp with FS off",
    0xA002: "c.fsdsp with FS off",
    0x2001: "c.addiw rd=x0",
    0x6101: "c.addi16sp zero displacement",
    0x6001: "c.lui zero immediate",
    cenc.c_jr(0) if False else 0x8002: "c.jr rs1=x0",
    cenc.c_lwsp(0, 4) if False else 0x4002: "c.lwsp rd=x0",
    0x6002: "c.ldsp rd=x0",
    cenc.c_sh(10, 11, 0) | (1 << 6): "c.sh misaligned selector",
    0x8000 | (1 << 12): "Zcb memory with reserved bit 12",
    0x9C79: "reserved Zcb arithmetic subencoding",
}


@pytest.mark.feature("IFU-RVC-006")
def test_reserved_encodings_are_illegal(rvc_expander):
    for word, label in RESERVED.items():
        fs = 1 if "FS off" in label else 0
        bits, ill = observe(rvc_expander, word, fs)
        assert ill == 1, f"{label} ({word:#06x}) must be illegal"
        del bits
    # A stack load with rd=x0 selects the reserved load opcode; return to a
    # legal stack load and back so the selector's low bits toggle both ways.
    for word in (cenc.c_lwsp(10, 4), 0x4002, cenc.c_lwsp(11, 8), 0x6002):
        observe(rvc_expander, word)


HINTS = [
    cenc.c_addi(0, 5),
    cenc.c_li(0, -3),
    cenc.c_mv(0, 11),
    cenc.c_add(0, 11),
    cenc.c_slli(0, 3),
    cenc.c_slli(10, 0),
    cenc.c_srli(10, 0),
    cenc.c_srai(10, 0),
    0x6081,  # c.mop hint-class nop
]


@pytest.mark.feature("IFU-RVC-007")
def test_hint_encodings_remain_legal(rvc_expander):
    for word in HINTS:
        expected = expand(word)
        assert not expected.ill and expected.hint, f"{word:#06x} is not a hint in the model"
        bits, ill = observe(rvc_expander, word)
        assert ill == 0, f"hint {word:#06x} must not raise an illegal instruction"
        del bits


# ---------------------------------------------------------------------------
# Broad model comparison and statelessness
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-RVC-002")
@pytest.mark.feature("IFU-RVC-003")
@pytest.mark.feature("IFU-RVC-004")
@pytest.mark.feature("IFU-RVC-006")
@pytest.mark.feature("IFU-RVC-008")
def test_random_compressed_words_match_the_model(rvc_expander):
    rng = random.Random(0x1F0)
    for _ in range(12000):
        word = rng.getrandbits(16)
        for fs in (0, 1):
            check(rvc_expander, word, expand(word, fs_is_off=bool(fs)), fs_is_off=fs)


@pytest.mark.feature("IFU-RVC-001")
def test_random_full_width_words_match_the_model(rvc_expander):
    rng = random.Random(0x2F0)
    for _ in range(2000):
        word = (rng.getrandbits(30) << 2) | 3
        for fs in (0, 1):
            assert observe(rvc_expander, word, fs) == (word, 0)


@pytest.mark.feature("IFU-RVC-009")
def test_expansion_is_stateless(rvc_expander):
    rng = random.Random(0x3F0)
    words = [rng.getrandbits(16) for _ in range(32)]
    first = {(word, fs): observe(rvc_expander, word, fs) for word in words for fs in (0, 1)}
    rng.shuffle(words)
    for word in words:
        for fs in (1, 0):
            assert observe(rvc_expander, word, fs) == first[(word, fs)]
    # Interleave marked illegal and valid words; a sticky illegal latch would
    # be visible here even if the decoder itself were combinational.
    for word in words[:8]:
        observe(rvc_expander, 0x0000)
        assert observe(rvc_expander, word, 0) == first[(word, 0)]
