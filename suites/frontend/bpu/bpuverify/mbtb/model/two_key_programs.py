"""Independent semantic axes, separate from optional physical replicas."""
from dataclasses import dataclass
from itertools import product
from bpuverify.mbtb.model.entry import CARRY_PATTERNS

MODES=('blocked','flow')
ORDERS=('first_second','second_first')
RULES=('distinct-original-identities','both-full-feedbacks-accepted','independent-full-entry-services',
    'fresh-forward-consumers','fresh-reverse-consumers','neighbors-and-originals-preserved')
PHYSICAL_COORDINATES=tuple(product(range(2),repeat=4))
REPRESENTATIVE_COORDINATES=((0,0,0,0),)


@dataclass(frozen=True,slots=True)
class Program:
    mode:str
    order:str
    pair:str
    coordinates:tuple=REPRESENTATIVE_COORDINATES[0]
    def __post_init__(self):
        if self.mode not in MODES or self.order not in ORDERS or self.pair not in CARRY_PATTERNS:
            raise ValueError('declared visibility, arrival order and complete target regions required')
        if type(self.coordinates) is not tuple or len(self.coordinates)!=4 or any(type(v) is not int or v not in (0,1) for v in self.coordinates):
            raise ValueError('physical replica needs four explicit binary coordinates')
    @property
    def label(self):return self.mode+'.'+self.order+'.'+self.pair
    def sample(self):return dict(zip(('context','align','bank','way'),self.coordinates),mode=self.mode,order=self.order,pair=self.pair)
    def state(self):return dict(semantic_profile=self.label,physical_replica=self.sample(),independent_keys=2,
        read_window_is_transaction_count=True,physical_replica_is_not_another_feature=True)


SEMANTIC_PROGRAMS=tuple(Program(m,o,p) for m,o,p in product(MODES,ORDERS,CARRY_PATTERNS))


def programs(profile):
    if profile not in ('production','physical'):raise ValueError('unknown two-key regression profile')
    coordinates=PHYSICAL_COORDINATES if profile=='physical' else REPRESENTATIVE_COORDINATES
    return tuple(Program(p.mode,p.order,p.pair,c) for c in coordinates for p in SEMANTIC_PROGRAMS)
