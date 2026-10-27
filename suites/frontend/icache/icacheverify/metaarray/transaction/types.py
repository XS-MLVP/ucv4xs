"""Typed transactions for the ICacheMetaArray DUT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetaArrayWrite:
    """One way-masked metadata refill."""

    set_index: int
    waymask: int
    phy_tag: int
    maybe_rvc_map: int = 0
    code: int = 0


@dataclass(frozen=True, slots=True)
class MetaArrayRead:
    """One or two cache lines, in request order."""

    set_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.set_indices) <= 2:
            raise ValueError("a meta read covers one or two lines")


@dataclass(frozen=True, slots=True)
class MetaArrayWay:
    """One way's metadata plus the valid bit that gates a tag match."""

    valid: int
    phy_tag: int
    maybe_rvc_map: int
    code: int
