"""Whole-vector ownership: one age owns both short and long experiences."""
from dataclasses import dataclass, asdict
from bpuverify.utage.model.dual_source import Program as LearningProgram, PC, EARLY, RELATIONS
from bpuverify.utage.model.semantic import Context, indices, tag

RULES = ('normally-learned-three-vectors', 'both-providers-discriminate-ages',
    'actual-four-input-lineage', 'one-owned-read-for-whole-vector',
    'complete-recovery-vector', 'independent-rematch-history',
    'current-versus-saved-content', 'complete-native-write-mask',
    'all-protection-and-neighbors', 'fresh-three-vector-consumers', 'immutable-originals')


@dataclass(frozen=True)
class Profile:
    name: str
    history: int
    warm: int
    relation: str

    pc = PC
    @property
    def context(self): return Context.from_recent(self.history)
    @property
    def indices(self): return indices(self.pc,self.context)
    @property
    def setup(self):
        return LearningProgram(self.relation,'reversed-holes','later-conditional','serial').steps[:2+self.warm]
    @property
    def prepared(self): return self.setup[-1].after
    def cell(self, table, value):
        return dict(valid=1,data_valid=1,index=self.indices[table],tag=tag(self.pc,self.context,table),
            position=value.position,counter=value.counter)


@dataclass(frozen=True)
class Program:
    stage: str
    relation: str
    retag: bool
    learning: bool

    def __post_init__(self):
        if self.stage not in ('s2','s3') or self.relation not in RELATIONS or type(self.retag) is not bool or type(self.learning) is not bool:
            raise ValueError('a declared stage, provider order and two Boolean lifecycle choices are required')
    rules = RULES
    @property
    def label(self): return '.'.join((self.stage,self.relation,'retag' if self.retag else 'match','learning' if self.learning else 'stable'))
    @property
    def profiles(self):
        # Selected age has interior confidence in BOTH directions. Learning
        # must change both counters, rather than hiding at saturation.
        warms = (2,1,0) if self.stage=='s2' else (1,2,0)
        return tuple(Profile(name,history,warm,self.relation) for name,history,warm in
            zip(('old','young','decoy'),(5,11,19),warms,strict=True))
    @property
    def target(self): return self.profiles[1 if self.stage=='s2' else 0]
    @property
    def decoy(self): return self.profiles[2]
    @property
    def history(self): return self.target.history ^ int(self.retag)
    def positions(self, seed=None):
        return tuple(p if seed is None or p==seed else None for p in (None,12,None,2))
    @property
    def latest(self):
        return tuple(value.teach(value,0) for value in self.target.prepared) if self.learning else self.target.prepared
    @property
    def feedbacks(self): return sum(len(p.setup) for p in self.profiles)+int(self.learning)
    def state(self):
        return dict(stage=self.stage,relation=self.relation,retag=self.retag,learning=self.learning,
            profiles=[asdict(p) for p in self.profiles],selected=self.target.name,
            slots=self.positions(),saved=[asdict(v) for v in self.target.prepared],
            current=[asdict(v) for v in self.latest],physical_enumeration=False,
            full_BPU_reachability_claimed=False)


PROGRAMS = tuple(Program(s,r,t,l) for s in ('s2','s3') for r in RELATIONS for t in (False,True) for l in (False,True))
OBLIGATIONS = tuple(p.label+'.'+rule for p in PROGRAMS for rule in RULES)
