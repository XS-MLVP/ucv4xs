"""Reference model for ICacheMetaArray.

The array is two *interleaved* metadata banks: set ``s`` lives in bank
``s & 1`` at index ``s >> 1``. Interleaving exists so two adjacent sets - exactly
the two halves of a 64-byte line when the fetch block is 32 bytes - can be
accessed concurrently, which is the documented purpose of
``NumInterleavedBank`` in the ICache parameters.

Architecture-level contract modelled here:

* a write refills one set, way-masked, and marks exactly those ways valid;
* a single-line read returns the four ways of one set;
* a double-line read returns two sets at once - each line may be any set, so the
  adapter must route each line to the bank that holds it and restore the
  original order on the response side. A caller must not be able to tell which
  bank served which line;
* ``flushAll`` (fence.i) clears every valid bit, because validity alone decides
  whether a tag may match;
* metadata and parity are stored verbatim.
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
class MetaArrayModel:
    sets: int = 256
    ways: int = 4
    banks: int = 2

    def __post_init__(self) -> None:
        if self.sets <= 0 or self.ways <= 0:
            raise ValueError("an array needs positive sets and ways")
        if self.banks <= 0 or self.sets % self.banks:
            raise ValueError("sets must be divisible by the interleaved bank count")
        self.memory: list[list[MetaEntry]] = [
            [MetaEntry(0, 0, 0) for _ in range(self.ways)] for _ in range(self.sets)
        ]
        self.valid: list[int] = [0] * self.sets

    # -- interleaved addressing --------------------------------------------
    def bank_of(self, set_index: int) -> int:
        return set_index % self.banks

    def index_of(self, set_index: int) -> int:
        return set_index // self.banks

    # -- operations --------------------------------------------------------
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

    def read_set(self, set_index: int) -> tuple[MetaWay, ...]:
        if not 0 <= set_index < self.sets:
            raise IndexError(f"set {set_index} outside 0..{self.sets - 1}")
        return tuple(
            MetaWay(self.valid[set_index] >> way & 1, self.memory[set_index][way])
            for way in range(self.ways)
        )

    def read(self, first: int, second: int | None = None) -> tuple[tuple[MetaWay, ...], ...]:
        """Single- or double-line read; order always matches the request.

        A double-line read is only well defined when the two sets live in
        different interleaved banks - that is the whole point of interleaving,
        and the adapter routes each line to the single bank that can serve it.
        Asking for two sets in the same bank is outside the contract (the RTL
        asserts on it in debug builds), so the model rejects it instead of
        inventing a result.
        """
        if second is None:
            return (self.read_set(first),)
        if self.bank_of(first) == self.bank_of(second):
            raise ValueError(
                f"double-line read needs one set per interleaved bank; "
                f"{first} and {second} share bank {self.bank_of(first)}")
        return (self.read_set(first), self.read_set(second))
