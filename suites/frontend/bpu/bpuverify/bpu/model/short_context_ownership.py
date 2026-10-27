"""Declared paths for a missing short-history sharing/isolation contract.

This is a stimulus/ownership plan, not another predictor reference model.
Eight real predecessor edges derive the contexts using the existing PHR
model. No DUT value, physical-coordinate sweep or forced folded history is
used. Existing EarlyDirectionSources/UtageReference remain the oracle.
"""
from dataclasses import dataclass
from functools import lru_cache

from bpuverify.bpu.model.history_working_set import ANCHOR, SHORT_POSITION, history_path
from bpuverify.bpu.model.ahead_working_set import Edge
from bpuverify.bpu.model.path_history import PathHistoryReference
from bpuverify.utage.model.semantic import ALT_FOLDS, TAG_FOLDS, Context, indices, tag


REQUIREMENT = 'BPU-INT-103'
OWNERS = ('left', 'right')
OLDER_PATHS = (0, 7)
RULES = ('shared-short-history', 'distinct-branch-ownership',
         'selective-protection-learning', 'fresh-both-history-consumers',
         'unrelated-branch-preserved', 'upper-protection-hold',
         'short-penalty-with-owned-long-allocation', 'immutable-original-snapshots')
PROFILES = ('left-selected', 'right-selected')
DIRECTION_PROFILES = tuple(selected+'.'+first for selected in PROFILES for first in ('left-first','right-first'))
DIRECTION_RULES = ('real-shared-short-owners','both-initial-NT-consumers','owned-opposite-guidance',
    'longer-companions-do-not-mask-short','selected-real-T-consumers','mixed-directions-preserved',
    'T-protection-and-direction-boundaries','actual-SRAM-after-turnaround','selected-real-NT-restoration',
    'NT-protection-and-direction-boundaries','all-final-short-consumers','immutable-original-evidence')
TURNAROUND_PATHS = (15,8,9,10)
RESTORATION_PATHS = (11,12,13,14)


@dataclass(frozen=True, slots=True)
class ShortContextPath:
    branch: str
    older_path: int
    branch_pc: int
    predecessors: tuple[int, ...]
    read_context: Context
    match_context: Context

    @property
    def read_indices(self):
        return indices(self.predecessors[-1], self.read_context)

    @property
    def tags(self):
        return tuple(tag(self.branch_pc, self.match_context, table) for table in range(2))

    @property
    def short_identity(self):
        return self.read_indices[0], self.tags[0], SHORT_POSITION

    @property
    def short_history(self):
        return tuple(self.match_context.folds[index] for index in (TAG_FOLDS[0], ALT_FOLDS[0]))

    @property
    def pcs(self): return self.predecessors

    @property
    def ordinal(self): return (0 if self.branch == 'left' else 512) + self.older_path

    @property
    def tail_variant(self): return self.branch

    def edges(self):
        return tuple(Edge(pc, self.pcs[index+1] if index+1 < len(self.pcs) else self.branch_pc, 3, max(7,pc%16))
                     for index, pc in enumerate(self.pcs))


def path(branch, older):
    if branch not in OWNERS or older not in (*OLDER_PATHS,*TURNAROUND_PATHS,*RESTORATION_PATHS,64):
        raise ValueError('one declared original, learning-only, or base-steering path required')
    second = branch == 'right'
    original = history_path(older)
    pcs = (*original.pcs[:-2], original.pcs[-2] ^ (0x10 if second else 0),
           original.pcs[-1] ^ (0x40 if second else 0))
    branch_pc = ANCHOR ^ (0x40 if second else 0)
    history, samples = PathHistoryReference(), [0]
    for index, pc in enumerate(pcs):
        target = pcs[index + 1] if index + 1 < len(pcs) else branch_pc
        samples.append(history.advance(taken=True, cfi_pc=(pc & ~15) + max(7,pc%16), target=target).history)
    return ShortContextPath(branch, older, branch_pc, pcs,
        Context.from_recent(samples[6]), Context.from_recent(samples[7]))


def declared_paths():
    # Two different program tails compensate their recent path contribution.
    # These fixed code locations are not a bank/set stimulus parameter.
    return tuple(path(branch, older) for branch in OWNERS for older in OLDER_PATHS)


def validate_paths(paths):
    if tuple((path.branch, path.older_path) for path in paths) != tuple(
            (branch, older) for branch in OWNERS for older in OLDER_PATHS):
        raise ValueError('all declared logical branch/path combinations are required')
    if len({path.branch_pc for path in paths}) != len(OWNERS):
        raise ValueError('different logical branches require different PCs')
    if len({path.short_history for path in paths}) != 1:
        raise ValueError('all paths must share a short history to distinguish PC ownership')
    identities = []
    for branch in OWNERS:
        group = tuple(path for path in paths if path.branch == branch)
        if len({path.branch_pc for path in group}) != 1:
            raise ValueError('older paths must belong to one branch PC')
        if len({path.short_identity for path in group}) != 1:
            raise ValueError('older paths must retain one shared short identity per branch')
        if len({path.read_indices[1] for path in group}) != len(OLDER_PATHS):
            raise ValueError('older paths must have distinct longer-history contexts')
        identities.append(group[0].short_identity)
    if len(set(identities)) != len(OWNERS) or len({identity[0] for identity in identities}) != len(OWNERS):
        raise ValueError('independent branches must coexist, not legally evict the same short row')
    return paths


def program():
    return validate_paths(declared_paths())


@dataclass(frozen=True, slots=True)
class BranchProgram:
    branch: str

    @property
    def helper(self): return path(self.branch, 64)

    def edges(self, cohort):
        if cohort != 0: raise ValueError('one actual branch program, not physical cohorts')
        return (Edge(self.helper.branch_pc, self.helper.pcs[0], 1, SHORT_POSITION), *self.helper.edges())


@dataclass(frozen=True, slots=True)
class ShortContextProgram:
    profile: str

    def __post_init__(self):
        if self.profile not in PROFILES: raise ValueError('unknown original branch selection')
        program()
        for branch in OWNERS:
            originals = tuple(item for item in self.paths if item.branch == branch)
            penalty, helper = self.penalty(branch), self.helper(branch)
            if penalty.short_identity != originals[0].short_identity:
                raise ValueError('learning-only path must update the same short record')
            if penalty.read_indices[1] in {item.read_indices[1] for item in originals}:
                raise ValueError('legal longer allocation cannot mask an original short consumer')
            if helper.read_indices[0] in {item.read_indices[0] for item in self.paths}:
                raise ValueError('base steering must not silently relearn either protected branch')

    @property
    def selected(self): return self.profile.removesuffix('-selected')

    @property
    def paths(self): return program()

    def helper(self, branch): return path(branch, 64)

    def penalty(self, branch): return path(branch, 15)

    def view(self, branch): return BranchProgram(branch)

    def state(self):
        return dict(profile=self.profile, selected=self.selected, branches=OWNERS,
                    consumer_paths=OLDER_PATHS, real_predecessors=8,
                    semantics='shared old-path learning within a branch; independent PCs across branches')


@dataclass(frozen=True, slots=True)
class ShortDirectionProgram(ShortContextProgram):
    """Independent branch experience survives a complete direction round trip.

    Learning-only older contexts share the short record. Their distinct long
    records must never substitute for the two original short consumers.
    """
    def __post_init__(self):
        if self.profile not in DIRECTION_PROFILES:
            raise ValueError('declared short-experience direction lifetime required')
        program()
        for branch in OWNERS:
            originals=tuple(item for item in self.paths if item.branch==branch)
            teaching=tuple(path(branch,older) for older in (*TURNAROUND_PATHS,*RESTORATION_PATHS))
            if any(item.short_identity!=originals[0].short_identity for item in teaching):
                raise ValueError('all declared outcomes must update the same short experience')
            if len({item.read_indices[1] for item in (*originals,*teaching)})!=len(originals)+len(teaching):
                raise ValueError('longer companions must not mask original consumers or one another')
            if self.helper(branch).read_indices[0]==originals[0].read_indices[0]:
                raise ValueError('base steering must not relearn the protected short record')

    @property
    def selected(self): return self.profile.split('.')[0].removesuffix('-selected')

    @property
    def learning_order(self): return OWNERS if self.profile.endswith('left-first') else OWNERS[::-1]

    @property
    def storage_paths(self): return tuple(next(item for item in self.paths if item.branch==branch) for branch in OWNERS)

    def reversal(self,branch,*,counter,protection,taken):
        from bpuverify.utage.model.usefulness_events import ProtectionState
        if branch!=self.selected or type(taken) is not bool:
            raise ValueError('only the declared selected branch changes direction')
        state=ProtectionState(counter,protection)
        if bool(state.taken)==taken:raise ValueError('declared direction is already present')
        result=[]
        for older in TURNAROUND_PATHS if taken else RESTORATION_PATHS:
            after=state.feedback(predicted=state.taken,base=int(not taken),actual=int(taken))
            result.append((path(branch,older),state,after))
            state=after
            if bool(state.taken)==taken:return tuple(result)
        raise ValueError('declared distinct original contexts cannot complete this direction change')

    def reversal_path(self,branch,older):
        if older not in (*TURNAROUND_PATHS,*RESTORATION_PATHS):
            raise ValueError('declared direction-learning context required')
        return path(branch,older)

    def state(self):
        return dict(profile=self.profile,selected=self.selected,learning_order=self.learning_order,
            consumer_paths=OLDER_PATHS,turnaround_paths=TURNAROUND_PATHS,restoration_paths=RESTORATION_PATHS,
            semantics='shared short experience changes direction and recovers without changing another branch',
            physical_enumeration=False,new_predictor_algorithm=False)


WORKING_SET_PROFILES=DIRECTION_PROFILES
WORKING_SET_RULES=('genuine-two-branch-paths','coexisting-short-experience','real-storage-pressure',
    'mixed-branch-owned-directions','selected-reversal','selected-restoration',
    'other-branch-preserved','other-paths-preserved','original-feedback-once',
    'no-longer-provider-substitution','SRAM-and-fresh-all-consumers','immutable-originals')


@dataclass(frozen=True,slots=True)
class WorkingSetPath(ShortContextPath):
    @property
    def tail_variant(self):return self.branch,tuple(self.predecessors[5:])


@lru_cache(maxsize=144)
def working_set_path(branch,incoming,older=None):
    from bpuverify.bpu.model.history_working_set import short_history_path,short_learning_path
    if branch not in OWNERS or type(incoming) is not int or not 0<=incoming<8:
        raise ValueError('declared branch and incoming program path required')
    original=short_history_path(incoming) if older is None else short_learning_path(incoming,older)
    pcs=list(original.pcs)
    if branch=='right':pcs[-2]^=0x10;pcs[-1]^=0x40
    branch_pc=ANCHOR^(0x40 if branch=='right' else 0)
    history,samples=PathHistoryReference(),[0]
    for index,pc in enumerate(pcs):
        samples.append(history.advance(taken=True,cfi_pc=(pc&~15)+max(7,pc%16),
            target=pcs[index+1] if index<7 else branch_pc).history)
    return WorkingSetPath(branch,incoming,branch_pc,tuple(pcs),
        Context.from_recent(samples[6]),Context.from_recent(samples[7]))


@dataclass(frozen=True,slots=True)
class WorkingSetBranch:
    branch:str
    @property
    def helper(self):return working_set_path(self.branch,0)
    def edges(self,cohort):
        if cohort!=0:raise ValueError('one actual code program, not physical cohorts')
        return (Edge(self.helper.branch_pc,self.helper.pcs[0],1,SHORT_POSITION),*self.helper.edges())


@dataclass(frozen=True,slots=True)
class ShortCrossBranchProgram:
    profile:str

    def __post_init__(self):
        if self.profile not in WORKING_SET_PROFILES:raise ValueError('declared correction owner and branch admission order required')
        originals={path.read_indices[1] for path in self.paths}
        indices={path.read_indices[0] for path in (*self.paths,*(self.helper(branch) for branch in OWNERS))}
        if len(indices)!=16:raise ValueError('all fourteen originals and two helpers must coexist without short replacement')
        for path in self.paths:
            companions=tuple(self.teaching_path(path,older) for older in (*TURNAROUND_PATHS,*RESTORATION_PATHS))
            if any(item.short_identity!=path.short_identity for item in companions):
                raise ValueError('older feedback must still belong to the same short experience')
            if len({item.read_indices[1] for item in companions})!=8 or any(item.read_indices[1] in originals for item in companions):
                raise ValueError('longer learning cannot replace an original short consumer')

    @property
    def selected(self):return self.profile.split('.')[0].removesuffix('-selected')
    @property
    def learning_order(self):return OWNERS if self.profile.endswith('left-first') else OWNERS[::-1]
    @property
    @lru_cache(maxsize=len(WORKING_SET_PROFILES))
    def paths(self):return tuple(working_set_path(branch,incoming) for branch in OWNERS for incoming in range(1,8))
    @property
    def storage_paths(self):return self.paths
    @property
    def mixed(self):return tuple(path for path in self.paths if path.branch==self.selected and path.older_path%2==0)
    @property
    def selected_path(self):return next(path for path in self.paths if path.branch==self.selected and path.older_path==1)
    def helper(self,branch):return working_set_path(branch,0)
    def view(self,branch):return WorkingSetBranch(branch)
    def identity_owner(self,path):return path.ordinal
    def teaching_path(self,path,older):return working_set_path(path.branch,path.older_path,older)

    def reversal(self,path,*,counter,protection,taken):
        from bpuverify.utage.model.usefulness_events import ProtectionState
        if path not in self.paths or type(taken) is not bool:raise ValueError('one original owner and explicit result required')
        state=ProtectionState(counter,protection)
        if bool(state.taken)==taken:raise ValueError('the requested direction is already learned')
        result=[]
        for older in TURNAROUND_PATHS if taken else RESTORATION_PATHS:
            after=state.feedback(predicted=state.taken,base=int(not taken),actual=int(taken))
            result.append((self.teaching_path(path,older),state,after));state=after
            if bool(state.taken)==taken:return tuple(result)
        raise ValueError('distinct real older sources cannot establish the requested reversal')

    def state(self):
        return dict(profile=self.profile,branches=2,short_identities=len(self.paths),
            selected=self.selected_path.ordinal,mixed=[path.ordinal for path in self.mixed],
            learning_order=self.learning_order,physical_enumeration=False,new_predictor_algorithm=False,
            semantic_event='cross-branch short experience survives storage pressure and selective reversal')
