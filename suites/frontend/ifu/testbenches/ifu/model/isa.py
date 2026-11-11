"""Independent RISC-V instruction encoders used to build stimuli and models.

These helpers encode architectural operations (what a program means), not
generated-RTL assignments.  Tests use them both to construct fetch windows and
to state the instruction word a reference model expects.
"""

from __future__ import annotations

MASK32 = (1 << 32) - 1


def _check(value: int, bits: int, name: str) -> int:
    if not 0 <= value < (1 << bits):
        raise ValueError(f"{name}={value:#x} does not fit in {bits} bits")
    return value


def i_type(opcode: int, rd: int, funct3: int, rs1: int, imm: int) -> int:
    _check(opcode, 7, "opcode")
    _check(rd, 5, "rd")
    _check(funct3, 3, "funct3")
    _check(rs1, 5, "rs1")
    _check(imm & 0xFFF, 12, "imm")
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def r_type(opcode: int, rd: int, funct3: int, rs1: int, rs2: int, funct7: int) -> int:
    _check(rs2, 5, "rs2")
    _check(funct7, 7, "funct7")
    return ((funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12)
            | (rd << 7) | opcode)


def s_type(opcode: int, funct3: int, rs1: int, rs2: int, imm: int) -> int:
    _check(imm & 0xFFF, 12, "imm")
    return (((imm >> 5) & 0x7F) << 25) | (rs2 << 20) | (rs1 << 15) \
        | (funct3 << 12) | ((imm & 0x1F) << 7) | opcode


def b_type(opcode: int, funct3: int, rs1: int, rs2: int, imm: int) -> int:
    if imm & 1:
        raise ValueError("branch immediate must be 2-byte aligned")
    imm &= 0x1FFF
    return (((imm >> 12) & 1) << 31) | (((imm >> 5) & 0x3F) << 25) \
        | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) \
        | (((imm >> 1) & 0xF) << 8) | (((imm >> 11) & 1) << 7) | opcode


def u_type(opcode: int, rd: int, imm20: int) -> int:
    _check(imm20, 20, "imm20")
    return (imm20 << 12) | (rd << 7) | opcode


def j_type(opcode: int, rd: int, imm: int) -> int:
    if imm & 1:
        raise ValueError("jump immediate must be 2-byte aligned")
    imm &= 0x1FFFFF
    return (((imm >> 20) & 1) << 31) | (((imm >> 1) & 0x3FF) << 21) \
        | (((imm >> 11) & 1) << 20) | (((imm >> 12) & 0xFF) << 12) \
        | (rd << 7) | opcode


#: Common instructions, expressed as architectural operations.
def addi(rd: int, rs1: int, imm: int) -> int:
    return i_type(0x13, rd, 0, rs1, imm)


def addiw(rd: int, rs1: int, imm: int) -> int:
    return i_type(0x1B, rd, 0, rs1, imm)


def add(rd: int, rs1: int, rs2: int) -> int:
    return r_type(0x33, rd, 0, rs1, rs2, 0)


def sub(rd: int, rs1: int, rs2: int) -> int:
    return r_type(0x33, rd, 0, rs1, rs2, 0x20)


def addw(rd: int, rs1: int, rs2: int) -> int:
    return r_type(0x3B, rd, 0, rs1, rs2, 0)


def subw(rd: int, rs1: int, rs2: int) -> int:
    return r_type(0x3B, rd, 0, rs1, rs2, 0x20)


def mul(rd: int, rs1: int, rs2: int) -> int:
    return r_type(0x33, rd, 0, rs1, rs2, 1)


def lui(rd: int, imm20: int) -> int:
    return u_type(0x37, rd, imm20 & 0xFFFFF)


def jal(rd: int, imm: int) -> int:
    return j_type(0x6F, rd, imm)


def jalr(rd: int, rs1: int, imm: int) -> int:
    return i_type(0x67, rd, 0, rs1, imm)


def beq(rs1: int, rs2: int, imm: int) -> int:
    return b_type(0x63, 0, rs1, rs2, imm)


def bne(rs1: int, rs2: int, imm: int) -> int:
    return b_type(0x63, 1, rs1, rs2, imm)


def load_bytes(funct3: int, rd: int, rs1: int, imm: int) -> int:
    return i_type(0x03, rd, funct3, rs1, imm)


def fp_load_bytes(funct3: int, rd: int, rs1: int, imm: int) -> int:
    return i_type(0x07, rd, funct3, rs1, imm)


def fp_store_bytes(funct3: int, rs1: int, rs2: int, imm: int) -> int:
    return s_type(0x27, funct3, rs1, rs2, imm)


def store_bytes(funct3: int, rs1: int, rs2: int, imm: int) -> int:
    return s_type(0x23, funct3, rs1, rs2, imm)


def nop() -> int:
    return addi(0, 0, 0)


def ebreak() -> int:
    return 0x00100073


def is_compressed(word: int) -> bool:
    return (word & 3) != 3
