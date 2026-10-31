"""Reference model for ICacheMetaInterleavedBank.

The bank stores, per set and per way, the line's metadata (physical tag, RVC
map) plus its parity code, together with one valid bit per way. Semantics come
from cache-structure invariants, not the RTL body:

* a way becomes valid exactly when a refill writes it, and the refill writes
  only the ways selected by ``waymask`` (way-masked fill, Hennessy & Patterson);
* a read returns every way's entry **and** its valid bit, because the tag
  comparison downstream must not treat a stale or never-written way as a hit;
* ``flushAll`` models a full invalidate (fence.i): every valid bit clears while
  the stored metadata may stay, since validity alone decides a hit;
* the macro is single-ported, so read-ready is low while a write is offered;
* the parity code is stored verbatim, so a corrupted code stays observable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetaEntry:
    phy_tag: int
    maybe_rvc_map: int
    code: int


@dataclass(frozen=True, slots=True)
class MetaWay:
    valid: int
    entry: MetaEntry


@dataclass
class MetaBankModel:
    sets: int
    ways: int

    def __post_init__(self) -> None:
        if self.sets <= 0 or self.ways <= 0:
            raise ValueError("a bank needs positive sets and ways")
        self.memory: list[list[MetaEntry]] = [
            [MetaEntry(0, 0, 0) for _ in range(self.ways)] for _ in range(self.sets)
        ]
        # One valid bit per set/way - a full invalidate is the only thing that
        # clears them, and only a refill sets them.
        self.valid: list[int] = [0] * self.sets

    def write(self, set_index: int, waymask: int, entry: MetaEntry) -> None:
        if not 0 <= set_index < self.sets:
            raise IndexError(f"set {set_index} outside 0..{self.sets - 1}")
        if waymask < 0 or waymask >> self.ways:
            raise ValueError(f"waymask {waymask:#x} does not fit {self.ways} ways")
        for way in range(self.ways):
            if waymask >> way & 1:
                self.memory[set_index][way] = entry
        self.valid[set_index] |= waymask

    def flush_all(self) -> None:
        self.valid = [0] * self.sets

    def read(self, set_index: int) -> tuple[MetaWay, ...]:
        if not 0 <= set_index < self.sets:
            raise IndexError(f"set {set_index} outside 0..{self.sets - 1}")
        return tuple(
            MetaWay(valid=self.valid[set_index] >> way & 1, entry=self.memory[set_index][way])
            for way in range(self.ways)
        )
