"""Typed transactions for the ICacheDataArray DUT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DataArrayWrite:
    """One way-masked refill, with one entry per data bank."""

    set_index: int
    waymask: int
    bank_entries: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if not self.bank_entries:
            raise ValueError("a refill needs at least one bank entry")


@dataclass(frozen=True, slots=True)
class DataArrayLine:
    """One cache line of a fetch: which banks it covers and which way to read."""

    bank_mask: int
    set_index: int
    way: int


@dataclass(frozen=True, slots=True)
class DataArrayRead:
    """One fetch request naming one or two lines."""

    lines: tuple[DataArrayLine, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.lines) <= 2:
            raise ValueError("a fetch covers one or two lines")
        for line in self.lines:
            if line.way < 0:
                raise ValueError("a way index cannot be negative")
