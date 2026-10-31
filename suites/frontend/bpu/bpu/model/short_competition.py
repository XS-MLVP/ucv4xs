"""Real incoming paths and declared competing owners, not a new predictor."""
from dataclasses import dataclass
from functools import lru_cache

from suites.frontend.bpu.bpu.model.history_working_set import ANCHOR,SHORT_POSITION,history_path,short_history_path
from suites.frontend.bpu.bpu.model.ahead_working_set import Edge
from suites.frontend.bpu.bpu.model.short_context_ownership import OWNERS,ShortContextPath
from suites.frontend.bpu.bpu.model.path_history import PathHistoryReference
from suites.frontend.bpu.utage.model.semantic import Context
from suites.frontend.bpu.abtb.model.semantic import coordinate as ahead_coordinate

PROFILES=tuple(owner+'.'+direction for owner in OWNERS for direction in ('old-NT','old-T'))
RULES=('shared-real-predecessors','complete-distinct-owners','old-qualified-protection',
    'protected-short-keeps-old-owner','new-own-long-fallback','old-errors-release-protection',
    'agreement-restores-confidence-not-protection','new-own-weak-confidence',
    'old-falls-back-without-borrowing-new','both-long-experiences-preserved',
    'actual-shared-SRAM-stages','original-sources-once-and-immutable')
RELEASE_PATHS=(15,8,9)
HELPER_PATHS={'left':64,'right':128}


@dataclass(frozen=True,slots=True)
class CompetitionPath(ShortContextPath):
    @property
    def tail_variant(self):return self.branch,tuple(self.predecessors[5:])
    @property
    def ahead_key(self):return ahead_coordinate(self.pcs[-1],self.read_context.folds[0])


@lru_cache(maxsize=16)
def incoming(branch,older):
    if branch not in OWNERS or type(older) is not int or older not in (0,7,*HELPER_PATHS.values(),*RELEASE_PATHS):
        raise ValueError('declared competing branch and genuine older path required')
    pcs=(short_history_path(1 if older==64 else 3).pcs
         if older in HELPER_PATHS.values() else history_path(older).pcs)
    pc=ANCHOR^(0x40 if branch=='right' else 0)
    history,samples=PathHistoryReference(),[0]
    for ordinal,address in enumerate(pcs):
        samples.append(history.advance(taken=True,cfi_pc=(address&~15)+max(7,address%16),
            target=pcs[ordinal+1] if ordinal<7 else pc).history)
    return CompetitionPath(branch,older,pc,pcs,Context.from_recent(samples[6]),Context.from_recent(samples[7]))


@dataclass(frozen=True,slots=True)
class Branch:
    branch:str
    @property
    def helper(self):return incoming(self.branch,HELPER_PATHS[self.branch])
    def edges(self,cohort):
        if cohort!=0:raise ValueError('one actual program, not physical coordinates')
        return (Edge(self.helper.branch_pc,self.helper.pcs[0],1,SHORT_POSITION),*self.helper.edges())


@dataclass(frozen=True,slots=True)
class Program:
    profile:str

    def __post_init__(self):
        if self.profile not in PROFILES:raise ValueError('one old owner and original direction required')
        a,b=self.original(self.old),self.original(self.new)
        if a.pcs!=b.pcs or a.read_indices!=b.read_indices or a.tags[0]==b.tags[0]:
            raise ValueError('real common predecessors must compete for one short row with distinct complete tags')
        if self.admission.short_identity!=b.short_identity:raise ValueError('new admission must retain the newcomers original short identity')
        paths=[incoming(self.old,older) for older in RELEASE_PATHS]
        if any(item.short_identity!=a.short_identity for item in paths):raise ValueError('each old error must retain the old short owner')
        if len({item.read_indices[1] for item in (*paths,a,self.admission)})!=5:
            raise ValueError('old releases and newcomer admission must not be masked by previous long records')
        if any(self.helper(branch).read_indices[0]==a.read_indices[0] for branch in OWNERS):
            raise ValueError('base steering must not teach the competing short record')
        helpers=tuple(self.helper(branch) for branch in OWNERS)
        if len({path.read_indices[0] for path in helpers})!=2 or len({path.read_indices[1] for path in helpers})!=2:
            raise ValueError('helper guidance must not create another short or long competition')
        if any(self.helper(branch).ahead_key!=self.original(branch).ahead_key for branch in OWNERS):
            raise ValueError('a real helper must steer the same Ahead prerequisite as its original branch')

    @property
    def old(self):return self.profile.split('.')[0]
    @property
    def new(self):return next(owner for owner in OWNERS if owner!=self.old)
    @property
    def old_taken(self):return self.profile.endswith('old-T')
    @property
    def new_taken(self):return not self.old_taken
    @property
    def learning_order(self):return self.old,self.new
    @property
    def paths(self):return tuple(self.original(branch) for branch in OWNERS)
    @property
    def storage_paths(self):return (self.original(self.old),)
    @property
    def admission(self):return incoming(self.new,7)
    def original(self,branch):return incoming(branch,0)
    def helper(self,branch):return incoming(branch,HELPER_PATHS[branch])
    def view(self,branch):return Branch(branch)
    def release(self,ordinal):return incoming(self.old,RELEASE_PATHS[ordinal])
    def state(self):
        return dict(profile=self.profile,old_owner=self.old,new_owner=self.new,old_taken=self.old_taken,
            old_strong_counter=7 if self.old_taken else 0,new_initial_counter=4 if self.new_taken else 3,
            same_real_predecessor=True,complete_short_tags=[path.tags[0] for path in self.paths],
            physical_enumeration=False,new_predictor_algorithm=False,full_FTQ_claimed=False)
