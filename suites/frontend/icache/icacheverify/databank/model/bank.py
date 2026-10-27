"""Reference model for ICacheDataBank.

Semantics come from the SRAM macro contract plus the cache-data invariants, not
from the RTL body:

* a bank holds ``nWays`` independent single-ported SRAMs, one way each, so a
  write with ``waymask`` updates only the selected ways and leaves the others
  untouched (standard way-masked cache write, Hennessy & Patterson ch. 2);
* a read returns every way's entry for the addressed set, because the hit
  decision is made downstream - the bank itself must not filter by waymask;
* the macro is single-ported, so a write and a read cannot be accepted in the
  same cycle; the bank advertises read-ready only while no write is offered;
* during the macro's reset sequence the array is not yet usable, so both
  directions must hold ready low until it completes;
* each entry carries its data word and its ECC/parity code as stored; the bank
  never recomputes the code, so a code written with the data must read back
  unchanged (that is what makes an injected single-bit error observable).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DataEntry:
    data: int
    code: int


@dataclass
class DataBankModel:
    sets: int
    ways: int

    def __post_init__(self) -> None:
        if self.sets <= 0 or self.ways <= 0:
            raise ValueError("a bank needs positive sets and ways")
        # memory[set][way]; uninitialised entries read as zero after reset.
        self.memory: list[list[DataEntry]] = [
            [DataEntry(0, 0) for _ in range(self.ways)] for _ in range(self.sets)
        ]

    def write(self, set_index: int, waymask: int, entry: DataEntry) -> None:
        """Write one entry into every way selected by ``waymask``."""
        if not 0 <= set_index < self.sets:
            raise IndexError(f"set {set_index} outside 0..{self.sets - 1}")
        if waymask < 0 or waymask >> self.ways:
            raise ValueError(f"waymask {waymask:#x} does not fit {self.ways} ways")
        for way in range(self.ways):
            if waymask >> way & 1:
                self.memory[set_index][way] = entry

    def read(self, set_index: int) -> tuple[DataEntry, ...]:
        """Every way's stored entry for ``set_index``."""
        if not 0 <= set_index < self.sets:
            raise IndexError(f"set {set_index} outside 0..{self.sets - 1}")
        return tuple(self.memory[set_index])

    def fill(self, set_index: int, entry_for_way) -> None:
        for way in range(self.ways):
            self.memory[set_index][way] = entry_for_way(way)
