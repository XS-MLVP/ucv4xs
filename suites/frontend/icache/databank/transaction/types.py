"""Typed transactions for the ICacheDataBank DUT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BankWrite:
    """One way-masked write into the data bank."""

    set_index: int
    waymask: int
    data: int
    code: int = 0


@dataclass(frozen=True, slots=True)
class BankRead:
    """A request for every way of one set."""

    set_index: int


@dataclass(frozen=True, slots=True)
class BankReadData:
    """Every way's stored word and code, as the bank presents them."""

    data: tuple[int, ...]
    code: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.data) != len(self.code):
            raise ValueError("data and code must describe the same ways")
