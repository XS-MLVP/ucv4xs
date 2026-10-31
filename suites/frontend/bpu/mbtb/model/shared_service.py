"""Different accepted requests can recover the same logical service owner."""
from dataclasses import dataclass
from itertools import product

SOURCES=('current-owner-control','old-miss-finds-retained-owner')
IDENTITIES=('ordinary-identity','zero-tag-only')
RULES=('genuine-owned-sources','complete-feedback-accepted','first-clear-meets-correction',
    'both-destination-services','fresh-survivor-and-neighbor','originals-and-unrelated-preserved')


@dataclass(frozen=True,slots=True)
class Program:
    source:str
    identity:str
    def __post_init__(self):
        if self.source not in SOURCES or self.identity not in IDENTITIES:
            raise ValueError('declared original provenance and identity boundary required')
    @property
    def shared(self):return self.source==SOURCES[1]
    @property
    def label(self):return self.source+'.'+self.identity
    @property
    def tag(self):return 0 if self.identity==IDENTITIES[1] else 1
    def state(self):return dict(source=self.source,identity=self.identity,
        first_clear=True,distinct_destination_records=True,owner_capacity_sufficient=True,
        source_nomination=0,logical_correction_owner=1 if self.shared else 0,
        physical_enumeration=False,full_FTQ_reachability_proven=False)


PROGRAMS=tuple(Program(*values) for values in product(SOURCES,IDENTITIES))
