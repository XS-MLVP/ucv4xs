"""Typed transactions for the ICacheMetaInterleavedBank DUT."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetaBankWrite:
    """One way-masked metadata fill."""

    set_index: int
    waymask: int
    phy_tag: int
    maybe_rvc_map: int = 0
    code: int = 0


@dataclass(frozen=True, slots=True)
class MetaBankRead:
    """A request for every way of one set."""

    set_index: int


@dataclass(frozen=True, slots=True)
class MetaBankWay:
    """One way's metadata plus the valid bit that gates its use."""

    valid: int
    phy_tag: int
    maybe_rvc_map: int
    code: int
