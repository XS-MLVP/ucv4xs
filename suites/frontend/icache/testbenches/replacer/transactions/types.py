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


# The DUT interleaves its two policy instances on the low vSetIdx bit and uses
# the remaining bits as the set index (ICacheReplacer port rule).  This is a
# property of the request encoding, so it is published with the transaction
# types rather than kept inside the reference model.
PORT_MASK = 0b1
SET_MASK = 0b1111_111

def port_of(vset_idx: int) -> int:
    return vset_idx & PORT_MASK

def set_of(vset_idx: int) -> int:
    return (vset_idx >> 1) & SET_MASK
