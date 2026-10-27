"""Typed transactions for the ICacheMainPipe DUT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FetchBlock:
    """One FTQ fetch request: a 64-byte window aligned to 32 bytes."""

    vaddr: int
    end_position: int
    ftq_idx: int
    taken: int = 0
    valid: int = 1

    def __post_init__(self) -> None:
        if self.vaddr & 0b1:
            raise ValueError("a fetch block starts on a 2-byte boundary")
        if not 0 <= self.end_position < 32:
            raise ValueError("end_position is an instruction slot in the block")

    @property
    def cross_line(self) -> int:
        return int(bool(self.vaddr & 0x20) and bool(self.end_position & 0x10))


@dataclass(frozen=True, slots=True)
class WayLookupLine:
    """The way-lookup result for one fetch request."""

    waymask: tuple[int, int]
    vset: tuple[int, int]
    ptag: int
    rvc_map: tuple[int, int] = (0, 0)
    meta_codes: tuple[int, int] = (0, 0)
    itlb_exception: int = 0
    is_mmio: int = 0
    itlb_pbmt: int = 0
    gpaddr: int = 0
    is_for_vs_non_leaf: int = 0
    valid: int = 1


@dataclass(frozen=True, slots=True)
class Refill:
    """A refill the miss unit would deliver for the requested line."""

    block: int
    vset: int
    data: int
    corrupt: int = 0
    denied: int = 0
    maybe_rvc_map: int = 0
