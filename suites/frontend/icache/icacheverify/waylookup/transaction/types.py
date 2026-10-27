"""Typed transactions for the ICacheWayLookup DUT.

Values are plain Python ints in RTL units. ``WayLookupEntry`` mirrors the
generated entry struct but stays independent of any signal binding, so the
model and the driver can share it without importing picker objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ItlbException:
    value: int = 0
    gpaddr: int = 0
    is_for_vs_non_leaf_pte: int = 0


@dataclass(frozen=True, slots=True)
class WayLookupEntry:
    """One prefetched way-lookup result, as written by the prefetch pipe."""

    vset_idx: tuple[int, int]
    waymask: tuple[int, int]
    ptag: int
    maybe_rvc_map: tuple[int, int]
    meta_codes: tuple[int, int]
    is_mmio: int = 0
    itlb_pbmt: int = 0
    exception: ItlbException = field(default_factory=ItlbException)

    def __post_init__(self) -> None:
        for name in ("vset_idx", "waymask", "maybe_rvc_map", "meta_codes"):
            value = getattr(self, name)
            if len(value) != 2:
                raise ValueError(f"{name} must hold one value per fetch port")


@dataclass(frozen=True, slots=True)
class WayLookupWrite:
    """A prefetch-port write beat carrying one entry for a single port."""

    entry: WayLookupEntry
    ftq_flag: int = 0
    ftq_value: int = 0


@dataclass(frozen=True, slots=True)
class WayLookupRead:
    """One entry observed on the way from the lookup to the main pipe."""

    valid: int
    entry: WayLookupEntry
