"""Typed transactions for the ICacheReplacer DUT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Touch:
    """One candidate way the lookup stage wants to mark as recently used."""

    vset_idx: int
    way: int


@dataclass(frozen=True, slots=True)
class VictimRequest:
    """A refill asking which way it should overwrite."""

    vset_idx: int


@dataclass(frozen=True, slots=True)
class VictimWay:
    """The way the policy selects for replacement."""

    way: int

    def __post_init__(self) -> None:
        if self.way < 0:
            raise ValueError("a victim way cannot be negative")
