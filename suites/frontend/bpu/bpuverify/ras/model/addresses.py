"""bpuverify.ras.model.addresses components."""

from __future__ import annotations


def return_addr(start_pc: int, position: int) -> int:
    return ((start_pc & ~0xF) + (position << 1) + 2) >> 1
