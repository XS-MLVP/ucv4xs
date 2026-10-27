"""Typed transactions for the ICacheMissUnit DUT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MissRequest:
    """A block the pipeline could not find in the cache."""

    block_paddr: int
    vset_idx: int


@dataclass(frozen=True, slots=True)
class RefillBeat:
    """One TileLink D-channel beat of a cache-line refill."""

    source: int
    corrupt: int = 0
    denied: int = 0

    def __post_init__(self) -> None:
        if self.source < 0:
            raise ValueError("a refill beat needs a non-negative source id")


@dataclass(frozen=True, slots=True)
class RefillResponse:
    """The response the DUT publishes when a refill completes."""

    block_paddr: int
    vset_idx: int
    waymask: int
    corrupt: int
    denied: int
    meta_write: int
    data_write: int
