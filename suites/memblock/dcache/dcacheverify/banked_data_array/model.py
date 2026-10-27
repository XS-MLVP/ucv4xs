"""Reference model for BankedDataArray (32 banks x 4 ways of 16-bit rows).

Index functions from DCacheWrapper.scala (modeId=1, DCacheSetDiv=1).
Only functional (non-DFT, non-pseudo-error) storage is modeled.
"""
from __future__ import annotations

BANKS = 32
WAYS = 4
SETS = 256
ROW_BITS = 16
VWORD_BANKS = 8


def dcache_bank(addr: int) -> int:
    # DCacheBankOffset = 1 (2-byte SRAM row), DCacheSetOffset = 6.
    return (addr >> 1) & 0x1F


def dcache_set(addr: int) -> int:
    hi = 0
    for bit in range(12, 48, 2):
        hi ^= (addr >> bit) & 0x3
    low = (addr >> 6) & 0x3F
    return ((hi & 0x3) << 6) | low


def bank_base(addr: int) -> int:
    return dcache_bank(addr) & ~(VWORD_BANKS - 1)


def set_class(value: int) -> str:
    if value == 0:
        return "zero"
    if value == SETS - 1:
        return "max"
    if value < 128:
        return "low"
    return "high"


class BankedDataArrayModel:
    def __init__(self) -> None:
        self.memory = [[[0] * BANKS for _ in range(WAYS)] for _ in range(SETS)]
        self.writes = 0
        self.reads = 0

    def reset(self) -> None:
        self.memory = [[[0] * BANKS for _ in range(WAYS)] for _ in range(SETS)]

    # ---------------------------------------------------------------- write
    def commit_write(self, wmask: int, data: list[int], dup_valid: int,
                     dup_way: list[int], dup_addr: list[int]) -> None:
        for bank in range(BANKS):
            if not ((wmask >> bank) & 1) or not ((dup_valid >> bank) & 1):
                continue
            index = dcache_set(dup_addr[bank])
            way = dup_way[bank].bit_length() - 1
            if not 0 <= way < WAYS:
                continue
            self.memory[index][way][bank] = data[bank] & 0xFFFF
        self.writes += 1

    # ---------------------------------------------------------------- read
    def read_result(self, addr: int, addr_dup: int, way_en: int, bank_mask: int,
                    previous: list[int] | None = None) -> list[int]:
        """Return the 8-bank response window for one read port.

        Banks whose mask bit is clear keep the previously latched response (the
        RTL response register is only updated for enabled banks through the
        bank_result mux); the previous window is supplied by the caller.
        """
        way = way_en.bit_length() - 1
        base = bank_base(addr)
        result = list(previous) if previous is not None else [0] * VWORD_BANKS
        for offset in range(VWORD_BANKS):
            bank = (base + offset) & 0x1F
            if not ((bank_mask >> bank) & 1):
                continue
            if not 0 <= way < WAYS:
                continue
            index = dcache_set(addr_dup if bank < BANKS // 2 else addr)
            result[offset] = self.memory[index][way][bank]
        self.reads += 1
        return result

    def line_result(self, addr: int, way_en: int, rmask: int) -> list[int]:
        way = way_en.bit_length() - 1
        index = dcache_set(addr)
        if not 0 <= way < WAYS:
            return [0] * BANKS
        return [self.memory[index][way][bank] if (rmask >> bank) & 1 else 0
                for bank in range(BANKS)]
