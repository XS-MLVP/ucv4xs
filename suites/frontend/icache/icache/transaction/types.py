"""Typed transactions at the whole-ICache interface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FetchIssue:
    """One FTQ fetch issue: up to two 64-byte fetch blocks (same 4 KiB page)."""

    vaddr: int
    end_position: int
    ftq_idx: int
    taken: int = 0
    valid: int = 1
    is_cross_line: int = 0

    def __post_init__(self) -> None:
        if self.vaddr & 0b1:
            raise ValueError("a fetch block starts on a 2-byte boundary")
        if not 0 <= self.end_position < 32:
            raise ValueError("end_position is an instruction slot in the block")


@dataclass(frozen=True, slots=True)
class ItlbTranslation:
    """The ITLB answer for one fetch issue (one 4 KiB page)."""

    paddr: int
    miss: int = 0
    pbmt: int = 0
    pf: int = 0
    gpf: int = 0
    af: int = 0
    gpaddr: int = 0


@dataclass(frozen=True, slots=True)
class Refill:
    """One TileLink refill the memory peer must return."""

    block: int
    data: int
    corrupt: int = 0
    denied: int = 0
