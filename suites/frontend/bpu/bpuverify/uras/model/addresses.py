"""bpuverify.uras.model.addresses components."""

from __future__ import annotations


def call_target(start_pc: int, position: int) -> int:
    # GuardedPc.addr omits architectural bit 0.  Fetch-block 16-byte
    # alignment therefore clears three bits in the picker-visible domain.
    return (start_pc & ~0x7) + position + 1
