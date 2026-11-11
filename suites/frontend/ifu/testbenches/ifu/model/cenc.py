"""Compressed-instruction encoders used to build fetch windows and stimuli.

The encoders are the inverse of the architectural field layouts, written from
the ISA encoding tables.  They do not consult the RTL or the reference
expansion model; a test that builds a window from these words and expects a
model expansion therefore has two independent descriptions of the intent.
"""

from __future__ import annotations


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _fits_signed(value: int, bits: int) -> bool:
    return -(1 << (bits - 1)) <= value < (1 << (bits - 1))


def _bits(value: int, first: int, last: int) -> int:
    """Bits [last:first] of an immediate, as an unshifted value."""

    width = last - first + 1
    return (value >> first) & ((1 << width) - 1)


def _signed6_hi(imm: int) -> int:
    return (imm & 0x20) << 7


# --------------------------------------------------------------------------
# Quadrant 0
# --------------------------------------------------------------------------
def c_addi4spn(rd: int, imm: int) -> int:
    _require(8 <= rd < 16 and 0 < imm < 1024 and imm % 4 == 0, "c.addi4spn fields")
    return ((_bits(imm, 4, 5)) << 11) | ((_bits(imm, 6, 9)) << 7) \
        | ((_bits(imm, 2, 2)) << 6) | ((_bits(imm, 3, 3)) << 5) | ((rd - 8) << 2)


def _c_lw_like(funct3: int, r_d: int, r_s1: int, imm: int) -> int:
    _require(8 <= r_d < 16 and 8 <= r_s1 < 16 and 0 <= imm < 128 and imm % 4 == 0,
             "compressed word memory fields")
    return (funct3 << 13) | ((_bits(imm, 3, 5)) << 10) | ((_bits(imm, 2, 2)) << 6) \
        | ((_bits(imm, 6, 6)) << 5) | ((r_s1 - 8) << 7) | ((r_d - 8) << 2)


def _c_ld_like(funct3: int, r_d: int, r_s1: int, imm: int) -> int:
    _require(8 <= r_d < 16 and 8 <= r_s1 < 16 and 0 <= imm < 256 and imm % 8 == 0,
             "compressed doubleword memory fields")
    return (funct3 << 13) | ((_bits(imm, 3, 5)) << 10) | ((_bits(imm, 6, 7)) << 5) \
        | ((r_s1 - 8) << 7) | ((r_d - 8) << 2)


def c_lw(rd_p: int, rs1_p: int, imm: int) -> int:
    return _c_lw_like(2, rd_p, rs1_p, imm)


def c_sw(rd_p: int, rs1_p: int, imm: int) -> int:
    return _c_lw_like(6, rd_p, rs1_p, imm)


def c_ld(rd_p: int, rs1_p: int, imm: int) -> int:
    return _c_ld_like(3, rd_p, rs1_p, imm)


def c_sd(rd_p: int, rs1_p: int, imm: int) -> int:
    return _c_ld_like(7, rd_p, rs1_p, imm)


def c_fld(rd_p: int, rs1_p: int, imm: int) -> int:
    return _c_ld_like(1, rd_p, rs1_p, imm)


def c_fsd(rd_p: int, rs1_p: int, imm: int) -> int:
    return _c_ld_like(5, rd_p, rs1_p, imm)


def c_lbu(rd: int, rs1: int, imm: int) -> int:
    _require(8 <= rd < 16 and 8 <= rs1 < 16 and 0 <= imm < 4, "c.lbu fields")
    return 0x8000 | ((imm & 1) << 6) | (((imm >> 1) & 1) << 5) | ((rs1 - 8) << 7) | ((rd - 8) << 2)


def c_lh(rd: int, rs1: int, imm: int) -> int:
    _require(8 <= rd < 16 and 8 <= rs1 < 16 and imm in (0, 2), "c.lh fields")
    return 0x8400 | (1 << 6) | ((imm >> 1) << 5) | ((rs1 - 8) << 7) | ((rd - 8) << 2)


def c_lhu(rd: int, rs1: int, imm: int) -> int:
    _require(8 <= rd < 16 and 8 <= rs1 < 16 and imm in (0, 2), "c.lhu fields")
    return 0x8400 | ((imm >> 1) << 5) | ((rs1 - 8) << 7) | ((rd - 8) << 2)


def c_sb(rd: int, rs1: int, imm: int) -> int:
    _require(8 <= rd < 16 and 8 <= rs1 < 16 and 0 <= imm < 4, "c.sb fields")
    return 0x8800 | ((imm & 1) << 6) | (((imm >> 1) & 1) << 5) | ((rs1 - 8) << 7) | ((rd - 8) << 2)


def c_sh(rd: int, rs1: int, imm: int) -> int:
    _require(8 <= rd < 16 and 8 <= rs1 < 16 and imm in (0, 2), "c.sh fields")
    return 0x8C00 | ((imm >> 1) << 5) | ((rs1 - 8) << 7) | ((rd - 8) << 2)


# --------------------------------------------------------------------------
# Quadrant 1
# --------------------------------------------------------------------------
def c_addi(rd: int, imm: int) -> int:
    _require(0 <= rd < 32 and _fits_signed(imm, 6), "c.addi fields")
    return _signed6_hi(imm) | ((imm & 0x1F) << 2) | (rd << 7) | 1


def c_nop() -> int:
    return 0x0001


def c_addiw(rd: int, imm: int) -> int:
    _require(1 <= rd < 32 and _fits_signed(imm, 6), "c.addiw fields")
    return _signed6_hi(imm) | ((imm & 0x1F) << 2) | (rd << 7) | (1 << 13) | 1


def c_li(rd: int, imm: int) -> int:
    _require(0 <= rd < 32 and _fits_signed(imm, 6), "c.li fields")
    return _signed6_hi(imm) | ((imm & 0x1F) << 2) | (rd << 7) | (2 << 13) | 1


def c_lui(rd: int, imm6: int) -> int:
    _require(0 < rd < 32 and rd != 2 and imm6 != 0 and _fits_signed(imm6, 6), "c.lui fields")
    return _signed6_hi(imm6) | ((imm6 & 0x1F) << 2) | (rd << 7) | (3 << 13) | 1


def c_addi16sp(imm: int) -> int:
    _require(_fits_signed(imm, 10) and imm != 0 and imm % 16 == 0, "c.addi16sp fields")
    value = imm & 0x3FF
    return ((value >> 9) & 1) << 12 | ((value >> 4) & 1) << 6 \
        | ((value >> 6) & 1) << 5 | ((value >> 7) & 3) << 3 \
        | ((value >> 5) & 1) << 2 | (2 << 7) | (3 << 13) | 1


def c_srli(rd: int, shamt: int) -> int:
    _require(8 <= rd < 16 and 0 <= shamt < 64, "c.srli fields")
    return ((shamt & 0x20) << 7) | ((shamt & 0x1F) << 2) | ((rd - 8) << 7) | (4 << 13) | 1


def c_srai(rd: int, shamt: int) -> int:
    _require(8 <= rd < 16 and 0 <= shamt < 64, "c.srai fields")
    return ((shamt & 0x20) << 7) | ((shamt & 0x1F) << 2) | ((rd - 8) << 7) | (1 << 10) | (4 << 13) | 1


def c_andi(rd: int, imm: int) -> int:
    _require(8 <= rd < 16 and _fits_signed(imm, 6), "c.andi fields")
    return _signed6_hi(imm) | ((imm & 0x1F) << 2) | ((rd - 8) << 7) | (2 << 10) | (4 << 13) | 1


def _ca(rd: int, rs2: int, low5: int) -> int:
    _require(8 <= rd < 16 and 8 <= rs2 < 16, "compressed CA fields")
    return 0x8C01 | (low5 << 5) | ((rs2 - 8) << 2) | ((rd - 8) << 7)


def c_sub(rd: int, rs2: int) -> int:
    return _ca(rd, rs2, 0)


def c_xor(rd: int, rs2: int) -> int:
    return _ca(rd, rs2, 1)


def c_or(rd: int, rs2: int) -> int:
    return _ca(rd, rs2, 2)


def c_and(rd: int, rs2: int) -> int:
    return _ca(rd, rs2, 3)


def c_subw(rd: int, rs2: int) -> int:
    _require(8 <= rd < 16 and 8 <= rs2 < 16, "c.subw fields")
    return 0x9C01 | ((rs2 - 8) << 2) | ((rd - 8) << 7)


def c_addw(rd: int, rs2: int) -> int:
    _require(8 <= rd < 16 and 8 <= rs2 < 16, "c.addw fields")
    return 0x9C21 | ((rs2 - 8) << 2) | ((rd - 8) << 7)


def c_mul(rd: int, rs2: int) -> int:
    _require(8 <= rd < 16 and 8 <= rs2 < 16, "c.mul fields")
    return 0x9C41 | ((rs2 - 8) << 2) | ((rd - 8) << 7)


def c_zext_b(rd: int) -> int:
    _require(8 <= rd < 16, "c_zext_b fields")
    return 0x9C61 | ((rd - 8) << 7)


def c_sext_b(rd: int) -> int:
    _require(8 <= rd < 16, "c_sext_b fields")
    return 0x9C65 | ((rd - 8) << 7)


def c_zext_h(rd: int) -> int:
    _require(8 <= rd < 16, "c_zext_h fields")
    return 0x9C69 | ((rd - 8) << 7)


def c_sext_h(rd: int) -> int:
    _require(8 <= rd < 16, "c_sext_h fields")
    return 0x9C6D | ((rd - 8) << 7)


def c_zext_w(rd: int) -> int:
    _require(8 <= rd < 16, "c_zext_w fields")
    return 0x9C71 | ((rd - 8) << 7)


def c_not(rd: int) -> int:
    _require(8 <= rd < 16, "c_not fields")
    return 0x9C75 | ((rd - 8) << 7)


def c_j(offset: int) -> int:
    _require(_fits_signed(offset, 12) and offset % 2 == 0, "c.j offset")
    value = offset & 0xFFF
    return 0xA001 | (((value >> 11) & 1) << 12) | (((value >> 4) & 1) << 11) \
        | (((value >> 8) & 3) << 9) | (((value >> 10) & 1) << 8) \
        | (((value >> 6) & 1) << 7) | (((value >> 7) & 1) << 6) \
        | (((value >> 1) & 7) << 3) | (((value >> 5) & 1) << 2)


def _c_branch(funct3: int, rs1: int, offset: int) -> int:
    _require(8 <= rs1 < 16 and _fits_signed(offset, 9) and offset % 2 == 0,
             "compressed branch fields")
    value = offset & 0x1FF
    return (funct3 << 13) | 1 | (((value >> 8) & 1) << 12) | (((value >> 3) & 3) << 10) \
        | (((value >> 6) & 3) << 5) | (((value >> 1) & 3) << 3) \
        | (((value >> 5) & 1) << 2) | ((rs1 - 8) << 7)


def c_beqz(rs1: int, offset: int) -> int:
    return _c_branch(6, rs1, offset)


def c_bnez(rs1: int, offset: int) -> int:
    return _c_branch(7, rs1, offset)


# --------------------------------------------------------------------------
# Quadrant 2
# --------------------------------------------------------------------------
def c_slli(rd: int, shamt: int) -> int:
    _require(0 <= rd < 32 and 0 <= shamt < 64, "c.slli fields")
    return ((shamt & 0x20) << 7) | ((shamt & 0x1F) << 2) | (rd << 7) | 2


def c_fldsp(rd: int, imm: int) -> int:
    _require(0 <= rd < 32 and 0 <= imm < 512 and imm % 8 == 0, "c.fldsp fields")
    return 0x2002 | (((imm >> 5) & 1) << 12) | (((imm >> 3) & 3) << 5) \
        | (((imm >> 6) & 7) << 2) | (rd << 7)


def c_lwsp(rd: int, imm: int) -> int:
    _require(1 <= rd < 32 and 0 <= imm < 256 and imm % 4 == 0, "c.lwsp fields")
    return 0x4002 | (((imm >> 5) & 1) << 12) | (((imm >> 2) & 7) << 4) \
        | (((imm >> 6) & 3) << 2) | (rd << 7)


def c_ldsp(rd: int, imm: int) -> int:
    _require(1 <= rd < 32 and 0 <= imm < 512 and imm % 8 == 0, "c.ldsp fields")
    return 0x6002 | (((imm >> 5) & 1) << 12) | (((imm >> 3) & 3) << 5) \
        | (((imm >> 6) & 7) << 2) | (rd << 7)


def c_jr(rs1: int) -> int:
    _require(1 <= rs1 < 32, "c.jr rs1")
    return 0x8002 | (rs1 << 7)


def c_mv(rd: int, rs2: int) -> int:
    _require(0 <= rd < 32 and 1 <= rs2 < 32, "c.mv fields")
    return 0x8002 | (rd << 7) | (rs2 << 2)


def c_ebreak() -> int:
    return 0x9002


def c_jalr(rs1: int) -> int:
    _require(1 <= rs1 < 32, "c.jalr rs1")
    return 0x9002 | (rs1 << 7)


def c_add(rd: int, rs2: int) -> int:
    _require(0 <= rd < 32 and 1 <= rs2 < 32, "c.add fields")
    return 0x9002 | (rd << 7) | (rs2 << 2)


def c_fsdsp(rs2: int, imm: int) -> int:
    _require(0 <= rs2 < 32 and 0 <= imm < 512 and imm % 8 == 0, "c.fsdsp fields")
    return 0xA002 | (((imm >> 3) & 7) << 10) | (((imm >> 6) & 7) << 7) | (rs2 << 2)


def c_swsp(rs2: int, imm: int) -> int:
    _require(0 <= rs2 < 32 and 0 <= imm < 256 and imm % 4 == 0, "c.swsp fields")
    return 0xC002 | (((imm >> 2) & 15) << 9) | (((imm >> 6) & 3) << 7) | (rs2 << 2)


def c_sdsp(rs2: int, imm: int) -> int:
    _require(0 <= rs2 < 32 and 0 <= imm < 512 and imm % 8 == 0, "c.sdsp fields")
    return 0xE002 | (((imm >> 3) & 7) << 10) | (((imm >> 6) & 7) << 7) | (rs2 << 2)
