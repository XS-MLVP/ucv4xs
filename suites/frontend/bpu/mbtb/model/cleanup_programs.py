"""Branch lifetimes, with physical placement kept out of semantic identities."""
from dataclasses import dataclass
from itertools import product

NEIGHBORS=('neighbor-established-before-correction','neighbor-arrives-with-correction')
CLEARS=('clear-still-pending','clear-already-served')
IDENTITIES={'zero-tag-only':'zero_tag','zero-position-only':'zero_position','nonzero-identity':'nonzero'}
RULES=('real-duplicate-and-independent-neighbor','complete-feedback-accepted',
    'clear-and-correction-both-preserved','survivor-and-neighbor-consumers',
    'reverse-consumers','originals-and-foreign-records-preserved')


@dataclass(frozen=True,slots=True)
class Program:
    neighbor:str
    clear:str
    identity:str
    coordinates:tuple=(0,0)
    def __post_init__(self):
        if self.neighbor not in NEIGHBORS or self.clear not in CLEARS or self.identity not in IDENTITIES:
            raise ValueError('declared branch and clear lifetimes plus identity boundary required')
        if type(self.coordinates) is not tuple or len(self.coordinates)!=2 or any(type(v) is not int or v not in (0,1) for v in self.coordinates):
            raise ValueError('two binary physical coordinates required')
    @property
    def label(self):return '.'.join((self.neighbor,self.clear,self.identity))
    def sample(self):return dict(align=self.coordinates[0],bank=self.coordinates[1],
        depth=NEIGHBORS.index(self.neighbor),shadow_state=('dirty','clean')[CLEARS.index(self.clear)],key=IDENTITIES[self.identity])
    def state(self):return dict(semantic_profile=self.label,neighbor_lifetime=self.neighbor,
        clear_lifetime=self.clear,identity_boundary=self.identity,physical_replica=self.sample(),
        physical_replica_is_not_another_feature=True)


SEMANTIC_PROGRAMS=tuple(Program(*values) for values in product(NEIGHBORS,CLEARS,IDENTITIES))


def programs(profile):
    if profile not in ('production','physical'):raise ValueError('unknown cleanup regression profile')
    coordinates=tuple(product(range(2),repeat=2)) if profile=='physical' else ((0,0),)
    return tuple(Program(p.neighbor,p.clear,p.identity,c) for c in coordinates for p in SEMANTIC_PROGRAMS)
