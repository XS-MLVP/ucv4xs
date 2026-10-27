"""Typed transactions for the ICacheMshr DUT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MissRequest:
    """A block the fetch pipeline could not find in the cache."""

    block_paddr: int
    vset_idx: int


@dataclass(frozen=True, slots=True)
class SecondaryHit:
    """Result of asking the MSHR whether a block is already in flight."""

    hit: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.hit:
            raise ValueError("a secondary-hit result needs at least one lookup")


@dataclass(frozen=True, slots=True)
class RefillInfo:
    """Bypass information published while an entry is live."""

    valid: int
    block_paddr: int
    vset_idx: int
    way: int
