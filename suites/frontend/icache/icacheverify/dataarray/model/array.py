"""Reference model for ICacheDataArray.

The array is 8 interleaved data banks. A 64-byte line is split evenly across the
banks by address, so a 32-byte fetch block occupies four consecutive banks; that
is why a request carries a per-line bank mask (``bankSel``) instead of a bank
index. Semantics modelled here come from the cache-data structure, not the RTL:

* **Address-to-bank mapping** - bank ``b`` holds byte range
  ``[b*rowBytes, (b+1)*rowBytes)`` of every line, so the bank set of a block is
  determined by the block's offset inside the line. This is the classic
  interleaved data array (Hennessy & Patterson, cache organisation).
* **Way-masked write** - a refill writes one entry per bank, and only into the
  ways selected by ``waymask``.
* **Multi-line read** - a request may name two lines (the two halves of a
  fetch), each with its own bank mask, set index and waymask. Every bank serves
  at most one of the two lines, which is exactly what the interleaving buys.
* **Per-request response** - each request receives the entry of the single way
  it selected on each of its banks; a bank the request did not cover reads as
  zero, because the downstream consumer only uses covered banks.
* **Single port** - read and write cannot be accepted in the same cycle.
* **Way ownership** - two requests may read different ways of the same bank, but
  they may not read the *same* way with different set indices, since one way can
  only present one set per access. The RTL asserts this in debug builds; the
  model rejects it as outside the contract.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DataEntry:
    data: int
    code: int = 0


@dataclass(frozen=True, slots=True)
class LineSelect:
    """One cache line of a read request."""

    bank_mask: int
    set_index: int
    waymask: int

    def covers(self, bank: int) -> int:
        return self.bank_mask >> bank & 1


@dataclass(frozen=True, slots=True)
class ReadRequest:
    """A fetch asking for up to two lines."""

    lines: tuple[LineSelect, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.lines) <= 2:
            raise ValueError("a data read covers one or two lines")
        for line in self.lines:
            if line.waymask == 0:
                raise ValueError("a line must select at least one way")
            if line.waymask & (line.waymask - 1):
                raise ValueError(
                    "one line may select only one way: the bank response is a "
                    "single entry per request")


@dataclass
class DataArrayModel:
    banks: int = 8
    sets: int = 256
    ways: int = 4

    def __post_init__(self) -> None:
        if self.banks <= 0 or self.sets <= 0 or self.ways <= 0:
            raise ValueError("an array needs positive banks, sets and ways")
        self.memory: list[list[list[DataEntry]]] = [
            [[DataEntry(0, 0) for _ in range(self.ways)] for _ in range(self.sets)]
            for _ in range(self.banks)
        ]

    def write(self, set_index: int, waymask: int,
              entries: tuple[DataEntry, ...]) -> None:
        if not 0 <= set_index < self.sets:
            raise IndexError(f"set {set_index} outside 0..{self.sets - 1}")
        if len(entries) != self.banks:
            raise ValueError(f"a write needs one entry per bank ({self.banks})")
        if waymask < 0 or waymask >> self.ways:
            raise ValueError(f"waymask {waymask:#x} does not fit {self.ways} ways")
        for bank in range(self.banks):
            for way in range(self.ways):
                if waymask >> way & 1:
                    self.memory[bank][set_index][way] = entries[bank]

    def read(self, requests: tuple[ReadRequest, ...]) -> tuple[tuple[DataEntry, ...], ...]:
        """One bank entry per request per bank, in request order."""
        if not 1 <= len(requests) <= 2:
            raise ValueError("the array serves one or two requests")
        # (bank, way) -> set index, so the ownership rule can be enforced.
        claimed: dict[tuple[int, int], int] = {}
        for request in requests:
            for bank in range(self.banks):
                covering = [line for line in request.lines if line.covers(bank)]
                if len(covering) > 1:
                    raise ValueError(
                        f"bank {bank} is covered by both lines of one request")
                if not covering:
                    continue
                line = covering[0]
                way = (line.waymask & -line.waymask).bit_length() - 1
                key = (bank, way)
                if key in claimed and claimed[key] != line.set_index:
                    raise ValueError(
                        f"bank {bank} way {way} requested twice with different sets "
                        f"({claimed[key]} and {line.set_index})")
                claimed[key] = line.set_index

        responses = []
        for request in requests:
            entries = []
            for bank in range(self.banks):
                covering = [line for line in request.lines if line.covers(bank)]
                if not covering:
                    entries.append(DataEntry(0, 0))
                    continue
                line = covering[0]
                way = (line.waymask & -line.waymask).bit_length() - 1
                entries.append(self.memory[bank][line.set_index][way])
            responses.append(tuple(entries))
        return tuple(responses)
