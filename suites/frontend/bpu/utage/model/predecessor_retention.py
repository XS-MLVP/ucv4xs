"""Many incoming control-flow edges share a target, not their read ancestors."""
from dataclasses import dataclass

from suites.frontend.bpu.utage.model.learning_persistence import Program as Lifetime,PC,SHORT_POSITION,PROFILES,MODES
from suites.frontend.bpu.utage.model.semantic import Context, training_folds,indices,tag
from suites.frontend.bpu.utage.transaction.types import UtageLookup

PHASES = ('allocate','reward','upper-protection','direction-boundary','saturated-reward','base-agreement')
RULES = ('distinct-predecessor-and-match-ancestors','real-original-feedback-once',
    'actual-versions-services-and-storage','reward-survives-turnover','saturated-learning-preserves-direction',
    'base-agreement-preserves-protection','declared-retention-and-SRAM-consumers','all-neighbors-and-originals-preserved')


@dataclass(frozen=True)
class Program(Lifetime):
    taken: bool = True

    def __post_init__(self):
        super().__post_init__()
        if type(self.taken) is not bool:
            raise ValueError('declared taken or not-taken learning direction required')

    @property
    def label(self):
        return self.profile+('.taken.' if self.taken else '.not-taken.')+self.mode

    def predecessor(self,key):
        # Fixed code layout for distinct incoming blocks. No bank/set number
        # or uncovered-row list participates in generation.
        return PC+0x180+0x30*self.histories.index(key)

    def lookup(self,key,table,*,phase=None):
        base = self.taken if phase=='base-agreement' else not self.taken
        return UtageLookup(PC,SHORT_POSITION,int(base),folded_history=0,
            index_pc=self.predecessor(key),index_history=key)

    def identity(self,key,table):
        request = self.lookup(key,table)
        return table,indices(request.read_pc,Context.from_recent(request.read_history))[table],\
            tag(request.pc,Context.from_recent(request.folded_history),table),SHORT_POSITION

    def expected(self,key,table,counter,*,phase=None):
        request = self.lookup(key,table,phase=phase)
        result = dict(indices=tuple(self.identity(key,t)[1] for t in (0,1)),
            folds=training_folds(Context.from_recent(request.folded_history)),valid=(1,0,0,0),
            positions=tuple(SHORT_POSITION+i for i in range(4)),base=request.base_taken,strong=0,
            hit=int(counter is not None))
        if counter is not None:
            result.update(provider=0,counter=counter,taken=int(counter>=4),predicted=int(counter>=4))
        return result

    def order(self,phase):
        if phase not in PHASES:
            raise ValueError('declared predecessor learning phase required')
        return tuple(reversed(self.histories)) if phase in ('reward','saturated-reward') else self.histories

    def counter(self,phase):
        return dict(zip(PHASES,(4,5,6,7,7,7) if self.taken else (3,2,1,0,0,0),strict=True))[phase]

    def actual(self,phase):
        if phase not in PHASES:
            raise ValueError('declared learning phase required')
        return int(self.taken)

    def protection(self,phase):
        result = [0]*1024
        value = 1 if phase=='allocate' else 2 if phase=='reward' else 3
        for key in self.histories:
            result[self.identity(key,0)[1]] = value
        return tuple(result)

    def state(self):
        return dict(profile=self.profile,mode=self.mode,taken=self.taken,count=self.count,match_pc=PC,match_history=0,
            predecessors=[dict(key=k,pc=self.predecessor(k),read_history=k,
                identity=self.identity(k,0)) for k in self.histories],phases=PHASES,
            physical_enumeration=False,full_FTQ_reachability_claimed=False,
            reads_and_matches_have_distinct_ancestors=True,tag_reference_truncated=False)
