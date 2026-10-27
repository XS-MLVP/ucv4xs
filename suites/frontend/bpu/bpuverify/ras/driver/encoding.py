"""bpuverify.ras.driver.encoding components."""

from __future__ import annotations


def encode_cfi_pc(pc: int) -> int:
    """Pc is a 50-bit byte address; only its fixed zero alignment bit is pruned."""

    if type(pc) is not int or not 0 <= pc < 1 << 50 or pc % 2:
        raise ValueError("cfi_pc must be an even unsigned 50-bit byte address")
    return pc // 2
