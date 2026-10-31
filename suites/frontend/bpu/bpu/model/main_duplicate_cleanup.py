"""A duplicate clear owns a destination; it is not a tag-zero branch."""
from dataclasses import dataclass
from suites.frontend.bpu.mbtb.model.semantic import Entry,Target,coordinate,tag
from suites.frontend.bpu.bpu.model.main_service import entry_payload

IDENTITIES=('nonzero-identity','zero-tag-and-position')
OVERLAPS=('cleanup-only','cleanup-and-learning')
PREPARATIONS=('neighbor-already-serviced','neighbor-learning-inflight')
RULES=('qualified-cold-originals','distinct-branch-shadow-turnover','natural-duplicate-versions',
    'genuine-duplicate-consumer','actual-destination-clear','declared-independent-learning-overlap',
    'complete-destination-services','fresh-survivor-and-neighbor','immutable-originals')


@dataclass(frozen=True,slots=True)
class Program:
    identity:str
    overlap:str
    preparation:str='neighbor-already-serviced'

    def __post_init__(self):
        if type(self.identity) is not str or self.identity not in IDENTITIES:raise ValueError('declared branch/invalid-record identity required')
        if type(self.overlap) is not str or self.overlap not in OVERLAPS:raise ValueError('declared cleanup/learning overlap required')
        if type(self.preparation) is not str or self.preparation not in PREPARATIONS:raise ValueError('declared other-branch learning lifetime required')

    @property
    def label(self):return self.identity+'.'+self.overlap+'.'+self.preparation
    @property
    def inflight(self):return self.preparation=='neighbor-learning-inflight'
    @property
    def concurrent(self):return self.overlap=='cleanup-and-learning'
    @property
    def pc(self):return 0x80000080+(0x8000 if self.identity=='nonzero-identity' else 0)
    @property
    def position(self):return 5 if self.identity=='nonzero-identity' else 0
    @property
    def neighbor(self):return self.pc+256
    @property
    def query_neighbor(self):return self.neighbor+3
    @property
    def old_target(self):return self.pc+0x1200
    @property
    def target(self):return self.pc+0x1600
    @property
    def neighbor_target(self):return self.neighbor+0x1800
    @property
    def updated_neighbor_target(self):return self.neighbor+0x1A00
    @property
    def intermediate_neighbor_target(self):return self.neighbor+0x1900
    @property
    def prepared_neighbor_target(self):return self.intermediate_neighbor_target if self.inflight else self.neighbor_target
    @property
    def cleared(self):return entry_payload(coordinate(self.pc)[2],Entry())
    @property
    def neighbor_effect(self):
        return entry_payload(coordinate(self.query_neighbor)[2],Entry(tag(self.neighbor),3,3,0,
            Target.encode(self.query_neighbor,self.updated_neighbor_target)))
    @property
    def expected_services(self):return ((),(),(self.neighbor_effect,) if self.concurrent else (),(self.cleared,))

    def state(self):
        return dict(identity=self.identity,overlap=self.overlap,preparation=self.preparation,pc=self.pc,position=self.position,
            neighbor=self.neighbor,original_target=self.old_target,survivor_target=self.target,
            neighbor_target=self.updated_neighbor_target if self.concurrent else self.prepared_neighbor_target,
            capacity_assumption=16,physical_coordinate_enumeration=False,full_FTQ_reachability_proved=False)
