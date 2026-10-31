"""Typed transactions for the ICachePrefetchPipe DUT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PrefetchBlock:
    """One FTQ prefetch request (64-byte window, 32-byte aligned)."""

    vaddr: int
    next_vaddr: int
    end_position: int
    ftq_idx: int
    is_cross_line: int = 0
    is_soft_prefetch: int = 0
    backend_exception: int = 0
    vset: tuple[int, int] = (0, 0)


@dataclass(frozen=True, slots=True)
class MetaLine:
    """One metadata array line as seen on a read port."""

    entries: tuple


@dataclass(frozen=True, slots=True)
class Refill:
    block: int
    vset: int
    waymask: int
    maybe_rvc_map: int = 0
    corrupt: int = 0
