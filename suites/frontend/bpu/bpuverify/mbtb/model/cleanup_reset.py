"""One branch identity reused across reset, not a bank/way matrix."""
from dataclasses import asdict,dataclass

PROFILES=('observed-not-consumed','registered-invalidation')
RULES=('genuine-distinct-target-duplicate','old-cleanup-stage-qualified','effective-reset-ends-old-obligation',
    'fresh-queries-have-no-old-identities','same-address-new-branch-survives','new-direction-learning-is-independent',
    'new-neighbor-and-old-snapshots-preserved')


@dataclass(frozen=True)
class Branch:
    pc:int
    target:int
    position:int
    kind:int


@dataclass(frozen=True)
class Program:
    profile:str

    def __post_init__(self):
        if self.profile not in PROFILES:raise ValueError('unknown cleanup/reset lifetime')

    @property
    def old(self):return Branch(0x40000800,0x40002340,5,2)
    @property
    def changed(self):return Branch(self.old.pc,self.old.target+0x400,self.old.position,self.old.kind)
    @property
    def neighbor(self):return Branch(self.old.pc+64,0x40004560,self.old.position,2)
    @property
    def new(self):return Branch(self.old.pc,0x40006780,self.old.position,1)
    @property
    def new_neighbor(self):return Branch(self.neighbor.pc,0x400089ac,2,3)

    def state(self):
        return dict(profile=self.profile,old=asdict(self.old),changed=asdict(self.changed),
            neighbor=asdict(self.neighbor),new=asdict(self.new),new_neighbor=asdict(self.new_neighbor),
            physical_enumeration=False)
