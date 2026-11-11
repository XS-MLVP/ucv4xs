"""suites.frontend.bpu.testbenches.ras.env.driver.encoding components."""

from __future__ import annotations


def encode_cfi_pc(pc: int) -> int:
    """GuardedPc is a 51-bit byte address; prune only fixed alignment bit 0."""

    if type(pc) is not int or not 0 <= pc < 1 << 51 or pc % 2:
        raise ValueError("cfi_pc must be an even unsigned 51-bit guarded byte address")
    return pc // 2
