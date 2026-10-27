from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Request:
    allocate: int = 0
    returns: tuple[int, ...] = ()
    reset: bool = False
    confirmation_mask: int | None = None

    @property
    def mask(self) -> int:
        return (1 << self.allocate) - 1 if self.confirmation_mask is None else self.confirmation_mask


@dataclass(frozen=True)
class Observation:
    reset: bool
    confirmation_mask: int
    return_mask: int
    slots: tuple[int, ...]
    can_allocate: tuple[bool, ...] | None
    occupied: int | None
    empty: bool | None


@dataclass(frozen=True)
class Expected:
    slots: tuple[int, ...]
    offered: int
    occupied: int
    empty: bool


@dataclass(frozen=True)
class Facts:
    allocated: tuple[int, ...] = ()
    returned: tuple[int, ...] = ()
    recycled: tuple[int, ...] = ()
    scenarios: tuple[str, ...] = ()
