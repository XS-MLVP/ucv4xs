"""Different accepted requests can recover the same logical service owner."""
from dataclasses import dataclass
from itertools import product
from suites.frontend.bpu.mbtb.model.cleanup import cleanup_way_plan
from suites.frontend.bpu.mbtb.model.replacement import MbtbFourWayLru
from suites.frontend.bpu.mbtb.model.semantic import coordinate,tag
from suites.frontend.bpu.models.configuration import MAIN_RETAINED

SOURCES=('current-owner-control','old-miss-finds-retained-owner')
IDENTITIES=('ordinary-identity','zero-tag-only')
RULES=('genuine-owned-sources','complete-feedback-accepted','first-clear-meets-correction',
    'both-destination-services','fresh-survivor-and-neighbor','originals-and-unrelated-preserved')


@dataclass(frozen=True,slots=True)
class OwnerPlan:
    original:int
    extra:int
    nomination:int
    correction:int
    keep:int
    clear:int
    capacity:int


def shared_service_owners(shared):
    """Derive request and retained owners only from the declared input prefix."""
    if type(shared) is not bool:
        raise ValueError('shared-service source must be a semantic bool')
    plan=cleanup_way_plan();neighbor=MbtbFourWayLru()
    original,extra=neighbor.allocate(),neighbor.allocate()
    assert (original,extra)==(plan['displacer'],plan['extra'])
    if shared:neighbor.touch(original)
    return OwnerPlan(plan['original'],extra,neighbor.victim if shared else extra,
        original if shared else extra,plan['keep'],plan['clear'],MAIN_RETAINED)


def shared_service_addresses(identity_tag):
    if type(identity_tag) is not int or identity_tag not in (0,1):
        raise ValueError('shared-service program requires its zero/nonzero tag pair')
    first=(1<<31)+(identity_tag<<15);neighbor=first+0x80
    assert coordinate(first)==(0,0,0) and coordinate(neighbor)==(0,0,1)
    assert tag(first)==tag(neighbor)==identity_tag
    return first,neighbor,(1<<31)+0x2340


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
    @property
    def owners(self):return shared_service_owners(self.shared)
    def state(self):return dict(source=self.source,identity=self.identity,
        first_clear=True,distinct_destination_records=True,owner_capacity_sufficient=True,
        source_nomination=self.owners.nomination,logical_correction_owner=self.owners.correction,
        clear_owner=self.owners.clear,retained_capacity=self.owners.capacity,
        physical_enumeration=False,full_FTQ_reachability_proven=False)


PROGRAMS=tuple(Program(*values) for values in product(SOURCES,IDENTITIES))
