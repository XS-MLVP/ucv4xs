"""Independent reference for DuplicatedTagArray.

The model stores 36-bit tags per (set, way) and produces the 43-bit SECDED
codeword with the same linear encoder the RTL uses. The encoder is written from
the constants in `DuplicatedTagArray.sv` (not learned from DUT output):

    T   = (tag & 35'h7FFFFFFFF) & 35'h556AAAD5B
    T3  = tag & 36'h99B33366D
    T6  = ((tag >> 1) & 32'hF1E1E3C7) << 1
    T9  = ((tag >> 4) & 32'hE03FC07F) << 4
    T12 = ((tag >> 11) & 15'h7FFF) << 11
    T15 = ((tag >> 26) & 10'h3FF) << 26
    ecc = {parity(T15)^parity(T12)^parity(T9)^parity(T6)^parity(T3)^parity(T)^parity(tag),
           parity(T15), parity(T12), parity(T9), parity(T6), parity(T3), parity(T)}
"""
from __future__ import annotations

SETS = 256
WAYS = 4
TAG_BITS = 36
ECC_BITS = 7
TAG_MASK = (1 << TAG_BITS) - 1
CODWIDTH = TAG_BITS + ECC_BITS


def parity(value: int) -> int:
    return value.bit_count() & 1


def encode_ecc(tag: int) -> int:
    if not 0 <= tag <= TAG_MASK:
        raise ValueError(f"tag out of range: {tag:#x}")
    t = (tag & 0x7FFFFFFFF) & 0x556AAAD5B
    t3 = tag & 0x99B33366D
    t6 = ((tag >> 1) & 0xF1E1E3C7) << 1
    t9 = ((tag >> 4) & 0xE03FC07F) << 4
    t12 = ((tag >> 11) & 0x7FFF) << 11
    t15 = ((tag >> 26) & 0x3FF) << 26
    top = (parity(t15) ^ parity(t12) ^ parity(t9) ^ parity(t6)
           ^ parity(t3) ^ parity(t) ^ parity(tag))
    return (top << 6) | (parity(t15) << 5) | (parity(t12) << 4) | (parity(t9) << 3)\
        | (parity(t6) << 2) | (parity(t3) << 1) | parity(t)


def codeword(tag: int) -> int:
    return (encode_ecc(tag) << TAG_BITS) | tag


class DuplicatedTagArrayModel:
    """256 sets x 4 ways of 36-bit tags; codewords are derived, never stored."""

    def __init__(self) -> None:
        self.tags = [[0] * WAYS for _ in range(SETS)]
        self.reads = 0
        self.writes = 0

    def reset(self) -> None:
        self.tags = [[0] * WAYS for _ in range(SETS)]

    def write(self, index: int, way_en: int, tag: int) -> None:
        if not 0 <= index < SETS:
            raise ValueError(f"set out of range: {index}")
        if not 0 <= way_en < (1 << WAYS):
            raise ValueError(f"way_en out of range: {way_en:#x}")
        if not 0 <= tag <= TAG_MASK:
            raise ValueError(f"tag out of range: {tag:#x}")
        for way in range(WAYS):
            if (way_en >> way) & 1:
                self.tags[index][way] = tag
        self.writes += 1

    def read(self, index: int) -> list[int]:
        if not 0 <= index < SETS:
            raise ValueError(f"set out of range: {index}")
        self.reads += 1
        return [codeword(tag) for tag in self.tags[index]]

    def expected(self, index: int) -> list[int]:
        return [codeword(tag) for tag in self.tags[index]]
