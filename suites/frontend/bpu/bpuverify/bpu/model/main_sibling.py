"""Unexecuted later conditional branches retain their learned direction."""
from dataclasses import dataclass

from bpuverify.bpu.model.main_service import PC, STREAM_PC
from bpuverify.mbtb.model.semantic import Entry, Target, coordinate, tag
from bpuverify.bpu.model.main_service import entry_payload
from bpuverify.mbtb.model.replacement import MbtbTwoWayLru


EARLIER, LATER, FALLBACK = 1, 5, 12
LATER_TARGET = PC + 0x1800
VERSIONS = (PC + 0x600, PC + (1 << 20) + 0x800, PC - (1 << 20) + 0xA00)
PHASES = ('pending', 'committed')
ORIGINS = ('current', 'old-cold')


@dataclass(frozen=True, slots=True)
class Program:
    phase: str
    origin: str

    def __post_init__(self):
        if self.phase not in PHASES or self.origin not in ORIGINS:
            raise ValueError('declared version visibility and original-source age required')

    @property
    def label(self):return self.phase + '.' + self.origin

    def effect(self, version):
        return entry_payload(coordinate(PC)[2],Entry(tag(PC),EARLIER,3,0,Target.encode(PC,VERSIONS[version])))

    def direction(self):
        # The declared learning order is later branch first, earlier branch
        # second. Its retained owner comes from the existing independent LRU,
        # not the incoming nomination or a sampled SRAM way.
        recency = MbtbTwoWayLru()
        recency.allocate()
        owner = recency.allocate()
        return dict(row=coordinate(PC)[2],mask=1<<owner,values={str(owner):2})

    def state(self):
        return dict(phase=self.phase,origin=self.origin,pc=PC,earlier=EARLIER,later=LATER,
                    origin_semantics='resident original, not newest live signals' if self.origin=='current' else 'original captured before either branch was learned',
                    later_direction='strong not-taken',expected_later_counter=0,
                    semantics='correcting an earlier taken branch must not relearn a later branch which did not execute')
