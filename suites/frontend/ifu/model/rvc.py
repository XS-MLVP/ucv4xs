"""Specification-derived reference expansion for the RVC decoder.

The model is written from the RISC-V compressed-instruction encoding rules
(C extension, Zca/Zcb forms, posted loads/stores, and FS-state legality), not
from the generated RTL.  It answers the architectural question: *which 32-bit
instruction does this codec produce, and is the encoding legal?*

Two classes of encoding need a note:

* **Hints** (for example ``c.addi x0, 0``) are architecturally no-ops but the
  specification allows a producer to canonicalise them.  The model marks them
  ``hint``; tests assert legality and only compare bits for defined encodings.
* **Reserved** encodings must be reported ``ill``.  The instruction word a
  decoder returns alongside ``ill`` is unobservable by contract and is not
  compared.

Floating-point forms are legal only when the FP state is enabled.  Compressed
integer forms are independent of ``fsIsOff``.
"""

from __future__ import annotations

from dataclasses import dataclass

from suites.frontend.ifu.model.isa import add, addw, addi, addiw, jal, jalr, beq, bne
from suites.frontend.ifu.model.isa import fp_load_bytes, fp_store_bytes, i_type, load_bytes, lui, mul, r_type
from suites.frontend.ifu.model.isa import store_bytes, sub, subw


@dataclass(frozen=True)
class Expansion:
    bits: int
    ill: bool
    hint: bool = False
    form: str = ""


def _sext(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def _hex(value: int) -> int:
    return value & 0xFFFFFFFF


def expand(inst: int, *, fs_is_off: bool = False) -> Expansion:
    """Expand one 32-bit fetch word per the compressed-instruction contract."""

    inst &= 0xFFFFFFFF
    quadrant = inst & 3
    if quadrant == 3:
        return Expansion(inst, False, form="rvi")

    f3 = (inst >> 13) & 7
    rd = (inst >> 7) & 31
    rs2 = (inst >> 2) & 31
    bit12 = (inst >> 12) & 1
    rd_p = 8 + ((inst >> 2) & 7)
    rs1_p = 8 + ((inst >> 7) & 7)
    rs2_p = 8 + ((inst >> 2) & 7)

    if quadrant == 0:
        if f3 == 0:  # c.addi4spn
            imm = (((inst >> 11) & 3) << 4 | ((inst >> 7) & 0xF) << 6
                   | ((inst >> 6) & 1) << 2 | ((inst >> 5) & 1) << 3)
            if imm == 0:
                return Expansion(0, True, form="c.addi4spn")
            return Expansion(_hex(addi(rd_p, 2, imm)), False, form="c.addi4spn")
        if f3 == 1:  # c.fld
            imm = (((inst >> 10) & 7) << 3) | (((inst >> 5) & 3) << 6)
            if fs_is_off:
                return Expansion(0, True, form="c.fld")
            return Expansion(_hex(fp_load_bytes(3, rd_p, rs1_p, imm)), False, form="c.fld")
        if f3 == 2:  # c.lw
            imm = (((inst >> 10) & 7) << 3) | (((inst >> 6) & 1) << 2) | (((inst >> 5) & 1) << 6)
            return Expansion(_hex(load_bytes(2, rd_p, rs1_p, imm)), False, form="c.lw")
        if f3 == 3:  # c.ld
            imm = (((inst >> 10) & 7) << 3) | (((inst >> 5) & 3) << 6)
            return Expansion(_hex(load_bytes(3, rd_p, rs1_p, imm)), False, form="c.ld")
        if f3 == 4:  # Zcb byte/halfword memory forms
            subop = (inst >> 10) & 3
            bit5 = (inst >> 5) & 1
            bit6 = (inst >> 6) & 1
            if bit12:
                return Expansion(0, True, form="c.zcb-mem")
            if subop == 0:  # c.lbu
                imm = (bit5 << 1) | bit6
                return Expansion(_hex(load_bytes(4, rd_p, rs1_p, imm)), False, form="c.lbu")
            if subop == 1:  # c.lh / c.lhu
                if bit6:
                    return Expansion(_hex(load_bytes(1, rd_p, rs1_p, bit5 << 1)), False, form="c.lh")
                return Expansion(_hex(load_bytes(5, rd_p, rs1_p, bit5 << 1)), False, form="c.lhu")
            if subop == 2:  # c.sb
                imm = (bit5 << 1) | bit6
                return Expansion(_hex(store_bytes(0, rs1_p, rs2_p, imm)), False, form="c.sb")
            # c.sh is legal only with bit6 clear, so the encoding is halfword aligned.
            if bit6:
                return Expansion(0, True, form="c.sh")
            return Expansion(_hex(store_bytes(1, rs1_p, rs2_p, bit5 << 1)), False, form="c.sh")
        if f3 == 5:  # c.fsd
            imm = (((inst >> 10) & 7) << 3) | (((inst >> 5) & 3) << 6)
            if fs_is_off:
                return Expansion(0, True, form="c.fsd")
            return Expansion(_hex(fp_store_bytes(3, rs1_p, rs2_p, imm)), False, form="c.fsd")
        if f3 == 6:  # c.sw
            imm = (((inst >> 10) & 7) << 3) | (((inst >> 6) & 1) << 2) | (((inst >> 5) & 1) << 6)
            return Expansion(_hex(store_bytes(2, rs1_p, rs2_p, imm)), False, form="c.sw")
        # c.sd
        imm = (((inst >> 10) & 7) << 3) | (((inst >> 5) & 3) << 6)
        return Expansion(_hex(store_bytes(3, rs1_p, rs2_p, imm)), False, form="c.sd")

    if quadrant == 1:
        if f3 == 0:  # c.addi / c.nop
            imm = _sext((bit12 << 5) | ((inst >> 2) & 0x1F), 6)
            if rd == 0:
                # c.nop is defined; c.addi with nonzero immediate is a hint.
                hint = imm != 0
                return Expansion(0x13, False, hint=hint, form="c.addi")
            return Expansion(_hex(addi(rd, rd, imm)), False, form="c.addi")
        if f3 == 1:  # c.addiw
            imm = _sext((bit12 << 5) | ((inst >> 2) & 0x1F), 6)
            if rd == 0:
                return Expansion(0, True, form="c.addiw")
            return Expansion(_hex(addiw(rd, rd, imm)), False, form="c.addiw")
        if f3 == 2:  # c.li
            imm = _sext((bit12 << 5) | ((inst >> 2) & 0x1F), 6)
            return Expansion(_hex(addi(rd, 0, imm)), False, hint=rd == 0, form="c.li")
        if f3 == 3:  # c.lui / c.addi16sp / c.mop
            if rd == 2:
                imm = (bit12 << 9) | (((inst >> 3) & 3) << 7) | (((inst >> 5) & 1) << 6) \
                    | (((inst >> 2) & 1) << 5) | (((inst >> 6) & 1) << 4)
                if imm == 0:
                    return Expansion(0, True, form="c.addi16sp")
                return Expansion(_hex(addi(2, 2, _sext(imm, 10))), False, form="c.addi16sp")
            imm6 = (bit12 << 5) | ((inst >> 2) & 0x1F)
            if imm6 == 0:
                # c.mop encodings are hint-class no-ops in Zcmop.
                if (rd & 1) and not (rd & 0x10):
                    return Expansion(0x13, False, hint=True, form="c.mop")
                return Expansion(0, True, form="c.lui")
            imm20 = _sext(imm6, 6) & 0xFFFFF
            return Expansion(_hex(lui(rd, imm20)), False, hint=rd == 0, form="c.lui")
        if f3 == 4:  # c.srli / c.srai / c.andi / c.sub...
            funct2 = (inst >> 10) & 3
            shamt = (bit12 << 5) | ((inst >> 2) & 0x1F)
            if funct2 == 0:
                return Expansion(_hex(i_type(0x13, rs1_p, 5, rs1_p, shamt)), False,
                                 hint=shamt == 0, form="c.srli")
            if funct2 == 1:
                return Expansion(_hex(i_type(0x13, rs1_p, 5, rs1_p, shamt | 0x400)), False,
                                 hint=shamt == 0, form="c.srai")
            if funct2 == 2:
                imm = _sext((bit12 << 5) | ((inst >> 2) & 0x1F), 6)
                return Expansion(_hex(i_type(0x13, rs1_p, 7, rs1_p, imm)), False, form="c.andi")
            selector = (bit12 << 2) | ((inst >> 5) & 3)
            if selector == 0:
                return Expansion(_hex(sub(rs1_p, rs1_p, rs2_p)), False, form="c.sub")
            if selector == 1:
                return Expansion(_hex(r_type(0x33, rs1_p, 4, rs1_p, rs2_p, 0)), False,
                                 form="c.xor")
            if selector == 2:
                return Expansion(_hex(r_type(0x33, rs1_p, 6, rs1_p, rs2_p, 0)), False,
                                 form="c.or")
            if selector == 3:
                return Expansion(_hex(r_type(0x33, rs1_p, 7, rs1_p, rs2_p, 0)), False,
                                 form="c.and")
            if selector == 4:
                return Expansion(_hex(subw(rs1_p, rs1_p, rs2_p)), False, form="c.subw")
            if selector == 5:
                return Expansion(_hex(addw(rs1_p, rs1_p, rs2_p)), False, form="c.addw")
            if selector == 6:
                return Expansion(_hex(mul(rs1_p, rs1_p, rs2_p)), False, form="c.mul")
            # Zcb arithmetic on the same encoding space.
            op = (inst >> 2) & 7
            if op == 0:  # c.zext.b
                return Expansion(_hex(i_type(0x13, rs1_p, 7, rs1_p, 0xFF)), False, form="c.zext.b")
            if op == 1:  # c.sext.b
                return Expansion(_hex(i_type(0x13, rs1_p, 1, rs1_p, 0x604)), False, form="c.sext.b")
            if op == 2:  # c.zext.h
                return Expansion(_hex(r_type(0x3B, rs1_p, 4, rs1_p, 0, 4)), False, form="c.zext.h")
            if op == 3:  # c.sext.h
                return Expansion(_hex(i_type(0x13, rs1_p, 1, rs1_p, 0x605)), False, form="c.sext.h")
            if op == 4:  # c.zext.w
                return Expansion(_hex(r_type(0x3B, rs1_p, 0, rs1_p, 0, 4)), False, form="c.zext.w")
            if op == 5:  # c.not
                return Expansion(_hex(i_type(0x13, rs1_p, 4, rs1_p, 0xFFF)), False, form="c.not")
            return Expansion(0, True, form="c.zcb")
        if f3 == 5:  # c.j
            imm = (bit12 << 11) | (((inst >> 8) & 1) << 10) | (((inst >> 9) & 3) << 8) \
                | (((inst >> 6) & 1) << 7) | (((inst >> 7) & 1) << 6) \
                | (((inst >> 2) & 1) << 5) | (((inst >> 11) & 1) << 4) \
                | (((inst >> 3) & 7) << 1)
            return Expansion(_hex(jal(0, _sext(imm, 12))), False, form="c.j")
        if f3 == 6:  # c.beqz
            imm = (bit12 << 8) | (((inst >> 5) & 3) << 6) | (((inst >> 2) & 1) << 5) \
                | (((inst >> 10) & 3) << 3) | (((inst >> 3) & 3) << 1)
            return Expansion(_hex(beq(rs1_p, 0, _sext(imm, 9))), False, form="c.beqz")
        # c.bnez
        imm = (bit12 << 8) | (((inst >> 5) & 3) << 6) | (((inst >> 2) & 1) << 5) \
            | (((inst >> 10) & 3) << 3) | (((inst >> 3) & 3) << 1)
        return Expansion(_hex(bne(rs1_p, 0, _sext(imm, 9))), False, form="c.bnez")

    # quadrant 2
    if f3 == 0:  # c.slli
        shamt = (bit12 << 5) | ((inst >> 2) & 0x1F)
        return Expansion(_hex(i_type(0x13, rd, 1, rd, shamt)), False,
                         hint=rd == 0 or shamt == 0, form="c.slli")
    if f3 == 1:  # c.fldsp
        imm = (bit12 << 5) | (((inst >> 5) & 3) << 3) | (((inst >> 2) & 7) << 6)
        if fs_is_off:
            return Expansion(0, True, form="c.fldsp")
        return Expansion(_hex(fp_load_bytes(3, rd, 2, imm)), False, form="c.fldsp")
    if f3 == 2:  # c.lwsp
        imm = (bit12 << 5) | (((inst >> 4) & 7) << 2) | (((inst >> 2) & 3) << 6)
        if rd == 0:
            return Expansion(0, True, form="c.lwsp")
        return Expansion(_hex(load_bytes(2, rd, 2, imm)), False, form="c.lwsp")
    if f3 == 3:  # c.ldsp
        imm = (bit12 << 5) | (((inst >> 5) & 3) << 3) | (((inst >> 2) & 7) << 6)
        if rd == 0:
            return Expansion(0, True, form="c.ldsp")
        return Expansion(_hex(load_bytes(3, rd, 2, imm)), False, form="c.ldsp")
    if f3 == 4:  # c.jr / c.mv / c.ebreak / c.jalr / c.add
        if bit12 == 0:
            if rs2 == 0:
                if rd == 0:
                    return Expansion(0, True, form="c.jr")
                return Expansion(_hex(jalr(0, rd, 0)), False, form="c.jr")
            return Expansion(_hex(addi(rd, rs2, 0)), False, hint=rd == 0, form="c.mv")
        if rs2 == 0:
            if rd == 0:
                return Expansion(0x00100073, False, form="c.ebreak")
            return Expansion(_hex(jalr(1, rd, 0)), False, form="c.jalr")
        return Expansion(_hex(add(rd, rd, rs2)), False, hint=rd == 0, form="c.add")
    if f3 == 5:  # c.fsdsp
        imm = (((inst >> 10) & 7) << 3) | (((inst >> 7) & 7) << 6)
        if fs_is_off:
            return Expansion(0, True, form="c.fsdsp")
        return Expansion(_hex(fp_store_bytes(3, 2, (inst >> 2) & 31, imm)), False, form="c.fsdsp")
    if f3 == 6:  # c.swsp
        imm = (((inst >> 9) & 0xF) << 2) | (((inst >> 7) & 3) << 6)
        return Expansion(_hex(store_bytes(2, 2, (inst >> 2) & 31, imm)), False, form="c.swsp")
    # c.sdsp
    imm = (((inst >> 10) & 7) << 3) | (((inst >> 7) & 7) << 6)
    return Expansion(_hex(store_bytes(3, 2, (inst >> 2) & 31, imm)), False, form="c.sdsp")
